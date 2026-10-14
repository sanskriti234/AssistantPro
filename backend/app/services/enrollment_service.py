"""
Student face enrollment - now backed by the real detect->liveness->embed
pipeline (app/services/face_pipeline_service.py). No simulated/random
results remain here (see git history for the earlier placeholder).

Design: validate_sample() runs real inference on each captured frame and
retains the resulting embedding server-side, keyed by student_id, in an
in-memory buffer (_pending_embeddings). finalize_enrollment() reads from
that buffer rather than trusting embeddings the client might send - the
frontend's existing contract (POST .../finalize with just a sample count)
is preserved unchanged; any embeddings field in that request body is
ignored, since the server already has the real ones from its own inference.
"""

from __future__ import annotations

import threading
import uuid

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import utcnow
from app.database.models import FaceEmbedding, FaceEnrollment, FaceEnrollmentStatus
from app.services import face_pipeline_service
from app.services.audit import log_action
from app.services.face_pipeline_service import FrameOutcome, PipelineUnavailable

REQUIRED_SAMPLES = 20
MIN_VALID_SAMPLES = 12

_MODEL_NAME = "SCRFD+ArcFace(AdaFace-slot)"  # see app/ml/face_embedder.py for why ArcFace, not AdaFace's own weights
_MODEL_VERSION = "buffalo-mbf-500m"

_buffer_lock = threading.Lock()
_pending_embeddings: dict[uuid.UUID, list[np.ndarray]] = {}

_OUTCOME_MESSAGES = {
    FrameOutcome.NO_FACE: "No face detected. Move closer and look at the camera.",
    FrameOutcome.MULTIPLE_FACES: "Multiple faces detected. Make sure only you are in frame.",
    FrameOutcome.SPOOF_DETECTED: "Liveness check failed. Use your own camera, not a photo or screen.",
    FrameOutcome.LOW_QUALITY: "Face quality too low. Improve lighting and hold steady.",
}


def validate_sample(frame_data_url: str, student_id: uuid.UUID) -> tuple[bool, str | None]:
    """
    Runs the real SCRFD -> liveness -> embedding pipeline on one captured
    frame. On success, the embedding is appended to this student's pending
    buffer (consumed by finalize_enrollment) and the sample counts as
    valid. Raises PipelineUnavailable (unchanged) if models aren't loaded -
    the route surfaces this as a 503, never a fake accept/reject.
    """
    if not frame_data_url or "," not in frame_data_url:
        return False, "Invalid frame payload"

    image = face_pipeline_service.decode_image(frame_data_url)
    result = face_pipeline_service.analyze_frame(image, check_liveness=True)

    if result.outcome != FrameOutcome.OK:
        return False, _OUTCOME_MESSAGES.get(result.outcome, "Sample rejected")

    with _buffer_lock:
        _pending_embeddings.setdefault(student_id, []).append(result.embedding)

    return True, None


def _consume_pending_embeddings(student_id: uuid.UUID) -> list[np.ndarray]:
    with _buffer_lock:
        embeddings = _pending_embeddings.pop(student_id, [])
    return embeddings


def finalize_enrollment(
    db: Session,
    student_id: uuid.UUID,
    valid_sample_count: int,
    embeddings: list[list[float]],  # accepted for API-contract compatibility; ignored - see module docstring
) -> dict:
    fe = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == student_id).first()
    if fe is None:
        fe = FaceEnrollment(student_id=student_id)
        db.add(fe)
        db.flush()

    real_embeddings = _consume_pending_embeddings(student_id)
    # The server's own count of successfully-embedded samples is the
    # authoritative one - never trust a client-supplied count either.
    actual_valid_count = len(real_embeddings)
    success = actual_valid_count >= MIN_VALID_SAMPLES

    fe.samples_processed = REQUIRED_SAMPLES
    fe.valid_samples = actual_valid_count

    if success:
        fe.status = FaceEnrollmentStatus.COMPLETE
        fe.enrolled_at = utcnow()
        fe.model_name = _MODEL_NAME
        fe.model_version = _MODEL_VERSION

        # Replace any previous embeddings for this enrollment (re-enrollment
        # supersedes, it does not accumulate).
        for old in list(fe.embeddings):
            db.delete(old)
        db.flush()

        settings = get_settings()
        dim = settings.face_embedding_dim
        for vec in real_embeddings:
            padded = np.zeros(dim, dtype=np.float32)
            n = min(len(vec), dim)
            padded[:n] = vec[:n]
            db.add(FaceEmbedding(
                enrollment_id=fe.id,
                embedding=padded.tolist(),
                quality_score=90.0,  # see README "Real AI model integration" - not yet derived from a real per-sample quality metric
                model_name=_MODEL_NAME,
                model_version=_MODEL_VERSION,
            ))

        log_action(db, user_id=student_id, action="FACE_ENROLLMENT_COMPLETED", entity_type="face_enrollment", entity_id=str(fe.id))
        db.commit()
        return {"status": "complete", "samplesProcessed": REQUIRED_SAMPLES, "validSamples": actual_valid_count}

    fe.status = FaceEnrollmentStatus.FAILED
    db.commit()
    return {
        "status": "failed",
        "samplesProcessed": REQUIRED_SAMPLES,
        "validSamples": actual_valid_count,
        "reason": "Insufficient face quality. Please try again in better lighting.",
    }
