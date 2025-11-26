import torch
import torchvision.transforms as T
from PIL import Image, ImageDraw, ImageFont
import io
import os
import logging
from .model import get_model  # your model definition


# -------------------------------------------------------------
# Load model once globally (safe absolute path)
# -------------------------------------------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Always resolve relative to this file’s folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "rcnn_model_v3.pth")

if not os.path.exists(MODEL_PATH):
    logging.error(f"Model file not found: {MODEL_PATH}")
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

logging.info(f"Loading model from {MODEL_PATH} (device={device})")

_model = get_model()

# load checkpoint (support training checkpoints that wrap state dict)
checkpoint = torch.load(MODEL_PATH, map_location=device)

# extract possible state dict keys used by common training scripts
if isinstance(checkpoint, dict):
    if "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        # might be already a raw state_dict (or a saved full model dict)
        state_dict = checkpoint
else:
    state_dict = checkpoint

# remove "module." prefix if present (from DataParallel)
if isinstance(state_dict, dict):
    normalized_state = {}
    for k, v in state_dict.items():
        new_k = k.replace("module.", "") if k.startswith("module.") else k
        normalized_state[new_k] = v
else:
    normalized_state = state_dict

# try strict loading first, fallback to non-strict and log
try:
    _model.load_state_dict(normalized_state)
except RuntimeError as e:
    logging.warning("Strict load_state_dict failed: %s. Retrying with strict=False.", e)
    try:
        _model.load_state_dict(normalized_state, strict=False)
    except Exception as e2:
        logging.error("Failed to load model state_dict even with strict=False: %s", e2)
        raise

_model.to(device)
_model.eval()

logging.info("Model loaded successfully and set to evaluation mode.")


# -------------------------------------------------------------
# Inference function
# -------------------------------------------------------------
def run_inference_from_bytes(image_bytes: bytes, score_threshold: float = 0.5):
    """
    Run inference on an image from bytes and return:
      - number of empty slots
      - annotated image bytes (JPEG)

    Args:
        image_bytes (bytes): Raw image data
        score_threshold (float): Confidence threshold for predictions

    Returns:
        (int, bytes): (number_of_empty_slots, annotated_image_bytes)
    """

    # ------------------------------
    # Load image
    # ------------------------------
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        logging.info("Image loaded successfully from bytes.")
    except Exception as e:
        logging.error(f"Failed to load image from bytes: {e}")
        raise ValueError(f"Failed to load image from bytes: {e}")

    transform = T.Compose([T.ToTensor()])
    img_tensor = transform(image).to(device)

    # ------------------------------
    # Run inference
    # ------------------------------
    with torch.no_grad():
        predictions = _model([img_tensor])

    pred = predictions[0]
    boxes = pred["boxes"].cpu()
    labels = pred["labels"].cpu()
    scores = pred["scores"].cpu()

    # Filter predictions above threshold
    valid = [(b, l, s) for b, l, s in zip(boxes, labels, scores) if s >= score_threshold]
    empty_slots = len(valid)

    logging.info(f"Detected {empty_slots} empty slots above threshold {score_threshold}")

    # ------------------------------
    # Draw predictions
    # ------------------------------
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()

    for box, label, score in valid:
        xmin, ymin, xmax, ymax = map(int, box.tolist())
        draw.rectangle(((xmin, ymin), (xmax, ymax)), outline="red", width=3)

        label_text = f"empty ({score:.2f})" if label.item() == 1 else f"unknown ({score:.2f})"
        text_bbox = draw.textbbox((xmin, ymin), label_text, font=font)
        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

        draw.rectangle(((xmin, ymin - text_h), (xmin + text_w, ymin)), fill="red")
        draw.text((xmin, ymin - text_h), label_text, fill="white", font=font)

    # ------------------------------
    # Convert to bytes
    # ------------------------------
    output_buffer = io.BytesIO()
    image.save(output_buffer, format="JPEG")
    annotated_image_bytes = output_buffer.getvalue()
    output_buffer.close()

    return empty_slots, annotated_image_bytes
