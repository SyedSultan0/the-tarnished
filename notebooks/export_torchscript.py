"""export_torchscript.py - Export the trained maize model to TorchScript.

Exports the EXACT trained FastAI model (no retraining, no architecture
change): loads models/maize_classifier.pkl with FastAI's load_learner(),
takes learn.model (.model is the raw PyTorch module), then traces it with
torch.jit.trace().

Run from the project root (FastAI + torch + torchvision required here;
only torch + torchvision are needed at Render runtime):

    python notebooks/export_torchscript.py
"""

from pathlib import Path

import torch
from fastai.vision.all import load_learner


# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

PKL_PATH = BASE_DIR / "models" / "maize_classifier.pkl"
OUTPUT_PATH = BASE_DIR / "backend" / "models" / "maize_classifier.pt"

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Load FastAI learner, trace learn.model, save
# ------------------------------------------------------------------

print("Loading FastAI learner from:", PKL_PATH)
if not PKL_PATH.exists():
    raise SystemExit(f"FastAI model file not found: {PKL_PATH}")

learn = load_learner(PKL_PATH)

print("Classes:", list(learn.dls.vocab))

model = learn.model

# CPU + eval mode (required before tracing).
model.to("cpu")
model.eval()

example_input = torch.randn(1, 3, 224, 224)

print("Tracing with torch.jit.trace ...")
with torch.no_grad():
    traced = torch.jit.trace(model, example_input)

traced.save(str(OUTPUT_PATH))

size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
print("TorchScript model saved to:", OUTPUT_PATH)
print(f"File size: {size_mb:.2f} MB")

