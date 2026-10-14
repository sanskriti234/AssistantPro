"""
Real-model tests for the face-recognition pipeline layer (app/ml/,
model_registry, face_pipeline_service). These load the ACTUAL downloaded
ONNX weights and run real inference - no mocking - against the reference
project's own labeled sample images.

Skipped entirely if the model files aren't present at backend/models/
(e.g. in an environment that hasn't run scripts/download_model_weights.sh
yet) - never faked, per Step 9/36's "do not claim live inference is
verified unless it was actually tested" and the analogous Google-credentials
pattern used elsewhere in this project.
"""

import os

import pytest

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SCRFD_PATH = os.path.join(MODELS_DIR, "det_500m.onnx")
EMBED_PATH = os.path.join(MODELS_DIR, "w600k_mbf.onnx")
LIVENESS_PATH = os.path.join(MODELS_DIR, "minifasnet_v2.onnx")

SAMPLES_DIR = "/home/claude/model_downloads/weights/Silent-Face-Anti-Spoofing-master/images/sample"
LIVE_IMAGE = os.path.join(SAMPLES_DIR, "image_T1.jpg")
SPOOF_IMAGE_1 = os.path.join(SAMPLES_DIR, "image_F1.jpg")
SPOOF_IMAGE_2 = os.path.join(SAMPLES_DIR, "image_F2.jpg")

_models_available = all(os.path.isfile(p) for p in (SCRFD_PATH, EMBED_PATH, LIVENESS_PATH))
_samples_available = all(os.path.isfile(p) for p in (LIVE_IMAGE, SPOOF_IMAGE_1, SPOOF_IMAGE_2))

pytestmark = pytest.mark.skipif(
    not (_models_available and _samples_available),
    reason="Real model weights/sample images not present - run scripts/download_model_weights.sh first",
)


@pytest.fixture(scope="module")
def monkeypatch_module():
    # pytest's built-in monkeypatch fixture is function-scoped; this is the
    # documented workaround for a module-scoped equivalent.
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def loaded_models(monkeypatch_module):
    from app.core.config import get_settings
    from app.services import model_registry

    monkeypatch_module.setenv("SCRFD_MODEL_PATH", SCRFD_PATH)
    monkeypatch_module.setenv("ADAFACE_MODEL_PATH", EMBED_PATH)
    monkeypatch_module.setenv("MINIFAS_MODEL_PATH", LIVENESS_PATH)
    get_settings.cache_clear()
    model_registry.reset_for_tests()
    model_registry.load_models()
    yield model_registry
    model_registry.reset_for_tests()
    get_settings.cache_clear()


def _load_image(path):
    import cv2

    return cv2.imread(path)


class TestDetection:
    def test_detects_one_face_in_live_sample(self, loaded_models):
        detector = loaded_models.get_detector()
        faces = detector.detect(_load_image(LIVE_IMAGE), confidence_threshold=0.5)
        assert len(faces) == 1
        assert faces[0].score > 0.5
        assert faces[0].landmarks.shape == (5, 2)

    def test_no_face_in_blank_image(self, loaded_models):
        import numpy as np

        detector = loaded_models.get_detector()
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = detector.detect(blank, confidence_threshold=0.5)
        assert len(faces) == 0

    def test_low_confidence_threshold_still_returns_real_score(self, loaded_models):
        detector = loaded_models.get_detector()
        faces = detector.detect(_load_image(LIVE_IMAGE), confidence_threshold=0.01)
        assert len(faces) >= 1
        assert 0.0 < faces[0].score <= 1.0


class TestEmbedding:
    def test_embedding_is_deterministic(self, loaded_models):
        from app.services import face_pipeline_service

        img = _load_image(LIVE_IMAGE)
        r1 = face_pipeline_service.analyze_frame(img, check_liveness=False)
        r2 = face_pipeline_service.analyze_frame(img, check_liveness=False)
        sim = face_pipeline_service.cosine_similarity(r1.embedding, r2.embedding)
        assert sim > 0.999

    def test_different_people_have_low_similarity(self, loaded_models):
        from app.services import face_pipeline_service

        r_live = face_pipeline_service.analyze_frame(_load_image(LIVE_IMAGE), check_liveness=False)
        r_spoof1 = face_pipeline_service.analyze_frame(_load_image(SPOOF_IMAGE_1), check_liveness=False)
        sim = face_pipeline_service.cosine_similarity(r_live.embedding, r_spoof1.embedding)
        # Different individuals - well below any reasonable same-person threshold.
        assert sim < 0.6

    def test_embedding_dimension_matches_config(self, loaded_models):
        embedder = loaded_models.get_embedder()
        assert embedder.embedding_dim == 512


class TestLiveness:
    def test_liveness_runs_and_returns_structured_result(self, loaded_models):
        from app.services import face_pipeline_service

        result = face_pipeline_service.analyze_frame(_load_image(LIVE_IMAGE), check_liveness=True)
        assert result.liveness_score is not None
        assert 0.0 <= result.liveness_score <= 1.0
        assert result.liveness_threshold is not None

    def test_liveness_score_present_for_spoof_sample_too(self, loaded_models):
        # NOTE (see backend/README.md "Real AI model integration" -
        # calibration caveat): this only asserts the pipeline runs
        # end-to-end and returns a real, structured score - it does NOT
        # assert is_live is correctly False for this spoof sample, because
        # that discrimination has not been successfully calibrated against
        # SCRFD-sourced boxes in this environment. See the README for the
        # full explanation of what "NOT VALIDATED" means here.
        from app.services import face_pipeline_service

        result = face_pipeline_service.analyze_frame(_load_image(SPOOF_IMAGE_1), check_liveness=True)
        assert result.liveness_score is not None
        assert 0.0 <= result.liveness_score <= 1.0


class TestPipelineUnavailable:
    def test_raises_when_models_not_loaded(self):
        from app.services import face_pipeline_service, model_registry

        model_registry.reset_for_tests()
        with pytest.raises(face_pipeline_service.PipelineUnavailable):
            face_pipeline_service.analyze_frame(_load_image(LIVE_IMAGE), check_liveness=True)
