
"""
model.py - FastAI Model Inference for THE TARNISHED

Loads the exported FastAI learner and provides maize disease
prediction with confidence handling.
"""

from pathlib import Path
import traceback

from fastai.vision.all import load_learner, PILImage


# ============================================================
# MODEL PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "maize_classifier.pkl"

print(f"🔍 Looking for model at: {MODEL_PATH}")
print(f"   File exists: {MODEL_PATH.exists()}")

if MODEL_PATH.exists():
    print(f"   File size: {MODEL_PATH.stat().st_size / 1024:.2f} KB")
else:
    print("   ❌ Model file not found!")


# ============================================================
# LOAD MODEL
# ============================================================

learn = None
learn_dls_vocab = None

try:
    learn = load_learner(MODEL_PATH)

    learn_dls_vocab = list(learn.dls.vocab)

    print("✅ Maize disease model loaded successfully!")
    print(f"   Classes: {learn_dls_vocab}")
    print(f"   Model type: {type(learn.model)}")

except Exception as e:
    print(f"❌ ERROR: Could not load maize disease model: {e}")
    traceback.print_exc()


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
