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


from io import BytesIO
from pathlib import Path
import traceback

import torch
from PIL import Image


# ============================================================
# MODEL PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Primary runtime model: TorchScript export at backend/models/maize_classifier.pt.
# Robust Path resolution works whether the app starts from repo root or from
# the backend/ directory (Render Root Directory = backend).
PT_PATH = Path(__file__).resolve().parent / "models" / "maize_classifier.pt"

# Legacy FastAI export kept only as a local/dev fallback reference.
PKL_PATH = BASE_DIR / "models" / "maize_classifier.pkl"

MODEL_PATH = PT_PATH

print(f"Looking for TorchScript model at: {PT_PATH}")
print(f"   File exists: {PT_PATH.exists()}")

if PT_PATH.exists():
    print(f"   File size: {PT_PATH.stat().st_size / 1024:.2f} KB")
else:
    print("   Model file not found!")
    if PKL_PATH.exists():
        print(f"   Legacy FastAI file present (dev fallback only): {PKL_PATH}")


# ============================================================
# LOAD MODEL (TorchScript only — no FastAI at runtime)
# ============================================================

torch_model = None

try:
    torch_model = torch.jit.load(str(PT_PATH), map_location="cpu")
    torch_model.eval()

    print("Maize disease model loaded successfully (TorchScript)!")
    print(f"   Classes: {CLASSES}")
    print(f"   Model type: {type(torch_model)}")

except Exception as e:
    print(f"ERROR: Could not load TorchScript maize model: {e}")
    traceback.print_exc()


# ============================================================
# PREPROCESSING (deterministic: RGB, 224x224, /255, ImageNet norm)
# ============================================================

def _preprocess_pil(pil_image):
    """Convert a PIL image to a normalized (1, 3, 224, 224) tensor."""
    image = pil_image.convert("RGB").resize((224, 224))
    pixels = list(image.getdata())
    width, height = image.size

    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)

    tensor = torch.zeros(3, height, width)
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[y * width + x]
            tensor[0, y, x] = r / 255.0
            tensor[1, y, x] = g / 255.0
            tensor[2, y, x] = b / 255.0

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

    FastAI handles the image preprocessing, resizing,
    normalization, tensor conversion and model inference.

    Args:
        image:
            PIL image, FastAI PILImage, or image path.

    Returns:
        Dictionary containing:
            disease
            confidence
            status
            probabilities
    """

    if learn is None:
        raise RuntimeError("Maize disease model is not loaded.")

    try:
        # ----------------------------------------------------
        # Convert normal PIL images to FastAI PILImage
        # ----------------------------------------------------

        if not isinstance(image, PILImage):
            image = PILImage.create(image)

        # ----------------------------------------------------
        # Let FastAI perform the complete inference pipeline.
        #
        # DO NOT manually create tensors here.
        # ----------------------------------------------------

        pred_class, pred_idx, probs = learn.predict(image)

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        confidence = float(probs[pred_idx])

        # ----------------------------------------------------
        # Confidence threshold
        # ----------------------------------------------------

        CONFIDENCE_THRESHOLD = 0.70

        if confidence >= CONFIDENCE_THRESHOLD:
            status = "high_confidence"
        else:
            status = "uncertain"

        # ----------------------------------------------------
        # All class probabilities
        # ----------------------------------------------------

        probabilities = {
            str(class_name): float(probability)
            for class_name, probability
            in zip(learn.dls.vocab, probs)
        }

        # ----------------------------------------------------
        # Return structured result
        # ----------------------------------------------------

        return {
            "disease": str(pred_class),
            "confidence": confidence,
            "status": status,
            "probabilities": probabilities
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

    # --------------------------------------------------------
    # Check model
    # --------------------------------------------------------

    if learn is None:

        print("❌ Model is not loaded!")
        print("   Check the model file path.")

    else:

        print("✅ Model is loaded!")
        print(f"   Classes: {learn_dls_vocab}")

        # ----------------------------------------------------
        # Find a sample image
        #
        # BASE_DIR points to:
        # THE TARNISHED/backend
        #
        # Therefore ../data points to:
        # THE TARNISHED/data
        # ----------------------------------------------------

        test_path = BASE_DIR / "data" / "Common_Rust"

        print(f"\n🔍 Looking for test images in:")
        print(f"   {test_path}")

        if test_path.exists():

            images = (
                list(test_path.glob("*.jpg"))
                + list(test_path.glob("*.JPG"))
                + list(test_path.glob("*.jpeg"))
                + list(test_path.glob("*.JPEG"))
                + list(test_path.glob("*.png"))
                + list(test_path.glob("*.PNG"))
            )

            if images:

                test_img_path = images[0]

                print(f"\n📸 Testing with:")
                print(f"   {test_img_path}")

                try:

                    # Pass the actual file path.
                    # predict_maize() will convert it to
                    # FastAI PILImage automatically.

                    result = predict_maize(test_img_path)

                    print("\n✅ Prediction successful!")
                    print(f"   Disease: {result['disease']}")
                    print(f"   Confidence: {result['confidence']:.4f}")
                    print(f"   Confidence %: {result['confidence'] * 100:.2f}%")
                    print(f"   Status: {result['status']}")

                    print("\n   All probabilities:")

                    for cls, prob in result["probabilities"].items():
                        print(f"     {cls}: {prob:.4f}")

                except Exception as e:

                    print(f"\n❌ Prediction failed: {e}")
                    traceback.print_exc()

            else:

                print("❌ No images found in Common_Rust.")

        else:

            print(f"❌ Test path not found:")
            print(f"   {test_path}")

    print("=" * 60)
