"""
Application-level model cache.

Models are loaded once (see app/main.py's startup hook -> load_models())
and reused for every recognition/enrollment request - never reloaded per
request. If a model file is missing or fails to load, `is_ready()` stays
False and the pipeline fails safely (Step 9: never fall back to a fake
result - see face_pipeline_service.py, which checks this before doing
anything).
"""

from __future__ import annotations

import logging
import os

from app.core.config import get_settings
from app.ml.face_embedder import FaceEmbedder
from app.ml.liveness_detector import MiniFASLivenessDetector
from app.ml.scrfd_detector import SCRFDDetector

logger = logging.getLogger("coresight.ml.model_registry")

_detector: SCRFDDetector | None = None
_embedder: FaceEmbedder | None = None
_liveness: MiniFASLivenessDetector | None = None
_load_error: str | None = None


def _providers() -> list[str]:
    settings = get_settings()
    device = settings.face_device.lower()
    if device == "cpu":
        return ["CPUExecutionProvider"]
    if device == "cuda":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    # "auto": prefer GPU if onnxruntime-gpu + a CUDA device are actually
    # available: CUDAExecutionProvider is only importable/usable when
    # onnxruntime-gpu (not the default CPU-only onnxruntime package) is
    # installed, so this is a genuine capability check, not a guess.
    try:
        import onnxruntime as ort

        if "CUDAExecutionProvider" in ort.get_available_providers():
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception:  # noqa: BLE001
        pass
    return ["CPUExecutionProvider"]


def load_models() -> None:
    """
    Called once at application startup. Never raises - a missing/broken
    model leaves is_ready() False (and load_error() populated) rather than
    crashing the whole application, so the rest of CoreSight (auth,
    batches, Google Forms, etc.) keeps working even if the ML weights
    aren't configured yet.
    """
    global _detector, _embedder, _liveness, _load_error

    settings = get_settings()
    providers = _providers()

    paths = {
        "SCRFD": settings.scrfd_model_path,
        "embedding": settings.adaface_model_path,
        "liveness": settings.minifas_model_path,
    }
    missing = [name for name, path in paths.items() if not path]
    if missing:
        _load_error = f"Model paths not configured: {', '.join(missing)} (see SCRFD_MODEL_PATH / ADAFACE_MODEL_PATH / MINIFAS_MODEL_PATH)"
        logger.warning("FACE_MODELS_NOT_CONFIGURED %s", _load_error)
        return

    not_found = [name for name, path in paths.items() if not os.path.isfile(path)]
    if not_found:
        _load_error = f"Model file(s) not found on disk: {', '.join(f'{n} ({paths[n]})' for n in not_found)}"
        logger.error("FACE_MODELS_LOAD_FAILED %s", _load_error)
        return

    try:
        _detector = SCRFDDetector(settings.scrfd_model_path, providers=providers)
        _embedder = FaceEmbedder(settings.adaface_model_path, providers=providers)
        _liveness = MiniFASLivenessDetector(settings.minifas_model_path, providers=providers)
        _load_error = None
        logger.info("FACE_MODELS_LOADED providers=%s embedding_dim=%s", providers, _embedder.embedding_dim)
    except Exception as e:  # noqa: BLE001 - a bad model file must not crash startup
        _detector = _embedder = _liveness = None
        _load_error = f"Failed to load model(s): {type(e).__name__}: {e}"
        logger.error("FACE_MODELS_LOAD_FAILED %s", _load_error)


def is_ready() -> bool:
    return _detector is not None and _embedder is not None and _liveness is not None


def load_error() -> str | None:
    return _load_error


def get_detector() -> SCRFDDetector:
    if _detector is None:
        raise RuntimeError("SCRFD detector is not loaded")
    return _detector


def get_embedder() -> FaceEmbedder:
    if _embedder is None:
        raise RuntimeError("Face embedder is not loaded")
    return _embedder


def get_liveness() -> MiniFASLivenessDetector:
    if _liveness is None:
        raise RuntimeError("Liveness detector is not loaded")
    return _liveness


def reset_for_tests() -> None:
    """Test-only hook to force a clean reload between test cases."""
    global _detector, _embedder, _liveness, _load_error
    _detector = _embedder = _liveness = None
    _load_error = None
