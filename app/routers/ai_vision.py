from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel
import base64
from typing import Optional
from pathlib import Path
import os

from app.ai_vision.ai_model_inference import run_inference_from_bytes

router = APIRouter(prefix="/ai", tags=["ai-vision"])


class InferenceResponse(BaseModel):
    empty_slots: int
    annotated_image_base64: str


class Base64Payload(BaseModel):
    image_base64: str
    score_threshold: Optional[float] = 0.5


@router.post("/infer", response_model=InferenceResponse)
def infer_from_base64(payload: Base64Payload = Body(...)):
    """Accept base64 image payload and return empty slot count + annotated image (base64)."""
    if not payload.image_base64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 is required")

    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64 image: {e}")

    try:
        count, annotated_bytes = run_inference_from_bytes(image_bytes, score_threshold=payload.score_threshold or 0.5)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Inference failed")

    annotated_b64 = base64.b64encode(annotated_bytes).decode("ascii")
    return {"empty_slots": count, "annotated_image_base64": annotated_b64}


class SaveResultPayload(BaseModel):
    transaction_id: str
    annotated_image_base64: str
    image_format: Optional[str] = "jpg"


@router.post("/result/save", response_model=dict)
def save_inference_result(payload: SaveResultPayload = Body(...)):
    """Save an annotated image (base64) associated with a transaction ID into resources/ai_vision_results."""
    if not payload.transaction_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transaction_id is required")
    if not payload.annotated_image_base64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="annotated_image_base64 is required")

    try:
        img_bytes = base64.b64decode(payload.annotated_image_base64)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64 image: {e}")

    # Prepare destination directory (ensure it's created under project root)
    results_dir = Path.cwd() / "resource" / "transaction_results"
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create results directory: {e}")
    if not results_dir.is_dir() or not os.access(results_dir, os.W_OK):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Results directory is not writable")

    # Create a filename using just the transaction id: {transaction_id}.{ext}
    ext = payload.image_format.lstrip(".").lower() or "jpg"
    filename = f"{payload.transaction_id}.{ext}"
    file_path = results_dir / filename

    try:
        with open(file_path, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to write image file: {e}")

    return {"saved_path": str(file_path), "filename": filename}