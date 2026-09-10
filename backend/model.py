"""
model.py - TorchScript Model Inference for THE TARNISHED.

Production runtime loads the traced TorchScript model
(backend/models/maize_classifier.pt) exported from the exact trained
FastAI learner. No FastAI is required at runtime.

Preprocessing matches the training pipeline:
RGB -> 224x224 -> float / 255 -> ImageNet normalization.
"""

from io import BytesIO
from pathlib import Path
import traceback

import torch
from PIL import Image


# ============================================================
# CLASSES / NORMALIZATION (exact training values)
# ============================================================

CLASSES = [
    "Common_Rust",
    "Gray_Leaf_Spot",
    "Healthy",
    "Northern_Corn_Leaf_Blight",
]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

CONFIDENCE_THRESHOLD = 0.70

# ============================================================
# MODEL PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Robust Path resolution works whether the app starts from repo root
# or from the backend/ directory (Render Root Directory = backend).
PT_PATH = Path(__file__).resolve().parent / "models" / "maize_classifier.pt"

MODEL_PATH = PT_PATH

print(f"Looking for TorchScript model at: {PT_PATH}")
print(f"   File exists: {PT_PATH.exists()}")

if PT_PATH.exists():
    print(f"   File size: {PT_PATH.stat().st_size / 1024 / 1024:.2f} MB")
else:
    print("   Model file not found!")


# ============================================================
# LOAD MODEL (TorchScript only — no FastAI at runtime)
# ============================================================

torch_model = None

try:
    torch_model = torch.jit.load(str(PT_PATH), map_location="cpu")
    torch_model.eval()

    print("Maize disease model loaded successfully (TorchScript)!")
    print(f"   Classes: {CLASSES}")

except Exception as e:
    print(f"ERROR: Could not load TorchScript maize model: {e}")
    traceback.print_exc()


# ============================================================
# PREPROCESSING (deterministic: RGB, 224x224, /255, ImageNet norm)
# ============================================================

def _preprocess_pil(pil_image):
    """Convert a PIL image to a normalized (1, 3, 224, 224) tensor."""
    image = pil_image.convert("RGB").resize((224, 224))

    # HWC uint8 -> CHW float / 255
    array = torch.frombuffer(image.tobytes(), dtype=torch.uint8)
    tensor = array.view(image.height, image.width, 3)
    tensor = tensor.permute(2, 0, 1).float() / 255.0

    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)

    tensor = (tensor - mean) / std
    return tensor.unsqueeze(0)


def _load_pil(image):
    """Accept PIL image, bytes, or filesystem path; return RGB PIL image."""
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, (bytes, bytearray)):
        return Image.open(BytesIO(bytes(image)))
    path = Path(str(image))
    if path.exists():
        return Image.open(path)
    return Image.open(BytesIO(bytes(image)))


# ============================================================
# PREDICTION
# ============================================================

def predict_maize(image):
    """
    Predict maize disease from an image.

    Accepts a filesystem path, bytes, or a PIL image.
    Returns the same structure as before:
        { disease, confidence, status, probabilities }
    """
    if torch_model is None:
        raise RuntimeError(
            "Maize model is not loaded. "
            f"Expected TorchScript model at: {PT_PATH}"
        )

    try:
        pil_image = _load_pil(image)
        tensor = _preprocess_pil(pil_image)

        with torch.no_grad():
            logits = torch_model(tensor)
            probs = torch.softmax(logits, dim=1)[0]

        pred_idx = int(torch.argmax(probs).item())
        confidence = float(probs[pred_idx].item())

        if confidence >= CONFIDENCE_THRESHOLD:
            status = "high_confidence"
        else:
            status = "uncertain"

        probabilities = {
            class_name: float(probs[i].item())
            for i, class_name in enumerate(CLASSES)
        }

        return {
            "disease": CLASSES[pred_idx],
            "confidence": confidence,
            "status": status,
            "probabilities": probabilities,
        }

    except Exception as e:
        print(f"❌ Prediction error: {e}")
        traceback.print_exc()
        raise


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("🧪 TESTING MODEL")
    print("=" * 60)

    if torch_model is None:
        print("❌ Model is not loaded! Check the model file path.")
    else:
        test_path = BASE_DIR / "data" / "Common_Rust"
        print(f"\n🔍 Looking for test images in: {test_path}")

        if test_path.exists():
            images = (
                list(test_path.glob("*.jpg"))
                + list(test_path.glob("*.JPG"))
                + list(test_path.glob("*.jpeg"))
                + list(test_path.glob("*.png"))
                + list(test_path.glob("*.PNG"))
            )

            if images:
                result = predict_maize(images[0])
                print(f"\n🔬 Disease: {result['disease']}")
                print(f"📊 Confidence: {result['confidence']:.4f}")
                print(f"📌 Status: {result['status']}")
                print(f"📈 Probabilities: {result['probabilities']}")
            else:
                print("No test images found.")
        else:
            print("Test data folder not found.")

        print("\n" + "=" * 60)
        print("✅ MODEL TEST COMPLETE")
        print("=" * 60)
