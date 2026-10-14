"""
Real face-recognition pipeline orchestration.

detect -> validate exactly one face -> liveness -> embed

This is the ONLY place the rest of CoreSight talks to the ML layer -
enrollment_service.py and attendance_service.py call functions here, never
app.ml.* directly, so model-specific details stay isolated (Step 2).

Every function in this module either returns a real result or raises
PipelineUnavailable - it never invents a recognition outcome when a model
isn't loaded (Step 9).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.services import model_registry


class PipelineUnavailable(Exception):
    """Raised when the ML models aren't loaded. Callers must surface this as a clear service-unavailable state, never a fake recognition result."""


class FrameOutcome(str, Enum):
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    SPOOF_DETECTED = "SPOOF_DETECTED"
    LOW_QUALITY = "LOW_QUALITY"
    OK = "OK"  # a single, live, good-quality face - embedding is populated


@dataclass
class FrameAnalysis:
    outcome: FrameOutcome
    detection_score: float | None = None
    liveness_score: float | None = None
    liveness_threshold: float | None = None
    embedding: np.ndarray | None = None
    bbox: tuple[float, float, float, float] | None = None


def decode_image(frame_data_url_or_bytes: str | bytes) -> np.ndarray:
    """Accepts a base64 data URL (as sent by the frontend) or raw bytes. Returns a BGR numpy array for OpenCV/ONNX Runtime."""
    if isinstance(frame_data_url_or_bytes, str):
        import base64

        header, _, b64data = frame_data_url_or_bytes.partition(",")
        raw = base64.b64decode(b64data or header)
    else:
        raw = frame_data_url_or_bytes

    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def analyze_frame(
    image: np.ndarray,
    *,
    check_liveness: bool,
    liveness_threshold: float | None = None,
    detection_threshold: float | None = None,
) -> FrameAnalysis:
    """
    Runs SCRFD -> (liveness) -> embedding on one frame.

    check_liveness=False is used by callers that only need
    detection+embedding; both enrollment and attendance pass True in
    practice (Step 5: never mark attendance solely from similarity without
    a passed liveness check).
    """
    if not model_registry.is_ready():
        raise PipelineUnavailable(model_registry.load_error() or "Face recognition models are not loaded")

    settings = get_settings()
    det_threshold = detection_threshold if detection_threshold is not None else settings.face_detection_threshold
    live_threshold = liveness_threshold if liveness_threshold is not None else settings.liveness_threshold

    detector = model_registry.get_detector()
    faces = detector.detect(image, confidence_threshold=det_threshold)

    if len(faces) == 0:
        return FrameAnalysis(outcome=FrameOutcome.NO_FACE)
    if len(faces) > 1:
        return FrameAnalysis(outcome=FrameOutcome.MULTIPLE_FACES)

    face = faces[0]
    if face.score < settings.face_quality_threshold:
        return FrameAnalysis(outcome=FrameOutcome.LOW_QUALITY, detection_score=face.score, bbox=face.bbox)

    result = None
    if check_liveness:
        liveness = model_registry.get_liveness()
        result = liveness.check(image, face.bbox, threshold=live_threshold)
        if not result.is_live:
            return FrameAnalysis(
                outcome=FrameOutcome.SPOOF_DETECTED, detection_score=face.score,
                liveness_score=result.score, liveness_threshold=result.threshold, bbox=face.bbox,
            )

    embedder = model_registry.get_embedder()
    embedding = embedder.extract(image, face.landmarks)

    return FrameAnalysis(
        outcome=FrameOutcome.OK,
        detection_score=face.score,
        liveness_score=result.score if result else None,
        liveness_threshold=result.threshold if result else None,
        embedding=embedding,
        bbox=face.bbox,
    )


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    from app.ml.align import cosine_similarity as _cos

    return _cos(a, b)
