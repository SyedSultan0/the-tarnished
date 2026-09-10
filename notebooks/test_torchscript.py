"""test_torchscript.py - Verify the TorchScript maize model.

1. Loads backend/models/maize_classifier.pt with torch.jit.load().
2. Finds one real image from the existing maize dataset.
3. Preprocesses deterministically (RGB, 224x224, /255, ImageNet norm).
4. Runs inference with torch.no_grad(), applies softmax.
5. Prints predicted class, confidence, all four probabilities.
6. Compares against the existing FastAI prediction for the SAME image
   (when fastai is installed; skipped gracefully otherwise).

Run from the project root:
    python notebooks/test_torchscript.py
"""

from pathlib import Path

import torch
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "backend" / "models" / "maize_classifier.pt"

CLASSES = [
    "Common_Rust",
    "Gray_Leaf_Spot",
    "Healthy",
    "Northern_Corn_Leaf_Blight",
]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def find_test_image():
    for class_dir in CLASSES:
        folder = BASE_DIR / "data" / class_dir
        if not folder.exists():
            continue
        images = (
            list(folder.glob("*.jpg"))
            + list(folder.glob("*.JPG"))
            + list(folder.glob("*.jpeg"))
            + list(folder.glob("*.JPEG"))
            + list(folder.glob("*.png"))
            + list(folder.glob("*.PNG"))
        )
        if images:
            return sorted(images)[0]
    raise SystemExit("No test image found under data/<class>/.")


def preprocess(image_path):
    img = Image.open(image_path).convert("RGB").resize((224, 224))
    pixels = list(img.getdata())
    w, h = img.size
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    tensor = torch.zeros(3, h, w)
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[y * w + x]
            tensor[0, y, x] = r / 255.0
            tensor[1, y, x] = g / 255.0
            tensor[2, y, x] = b / 255.0
    tensor = (tensor - mean) / std
    return tensor.unsqueeze(0)


print("Loading TorchScript model from:", MODEL_PATH)
if not MODEL_PATH.exists():
    raise SystemExit(f"TorchScript file not found: {MODEL_PATH}")
model = torch.jit.load(str(MODEL_PATH), map_location="cpu")
model.eval()
size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
print(f"Loaded OK. File size: {size_mb:.2f} MB")

test_image = find_test_image()
print("Test image:", test_image)

batch = preprocess(test_image)
with torch.no_grad():
    logits = model(batch)
probs = torch.softmax(logits, dim=1)[0]
pred_idx = int(torch.argmax(probs))
confidence = float(probs[pred_idx])

print("\n--- TorchScript prediction ---")
print(f"Predicted class: {CLASSES[pred_idx]}")
print(f"Confidence: {confidence:.4f} ({confidence * 100:.2f}%)")
print("All probabilities:")
for name, p in zip(CLASSES, probs.tolist()):
    print(f"  {name}: {float(p):.4f}")

print("\n--- FastAI comparison (same image) ---")
try:
    from fastai.vision.all import load_learner

    pkl = BASE_DIR / "models" / "maize_classifier.pkl"
    learn = load_learner(pkl)
    pred_class, pred_idx_fa, probs_fa = learn.predict(str(test_image))
    conf_fa = float(probs_fa[int(pred_idx_fa)])
    print(f"FastAI predicted class: {pred_class}")
    print(f"FastAI confidence: {conf_fa:.4f} ({conf_fa * 100:.2f}%)")
    print("FastAI probabilities:")
    for name, p in zip(learn.dls.vocab, probs_fa.tolist()):
        print(f"  {name}: {float(p):.4f}")
    match = str(pred_class) == CLASSES[pred_idx]
    print(f"\nTop-1 match: {'YES' if match else 'NO'}")
    if not match:
        print("NOTE: classes differ but both pipelines ran; "
              "inspect preprocessing before deploying.")
except ImportError:
    print("fastai is not installed here; FastAI comparison skipped.")
    print("(Export environment already validated; Render uses TorchScript.)")
except Exception as exc:
    print(f"FastAI comparison failed: {exc}")
