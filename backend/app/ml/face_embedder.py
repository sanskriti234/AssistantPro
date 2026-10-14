"""
Face embedding extraction via ONNX Runtime.

LIMITATION - documented substitute, not a silent swap (see
backend/README.md "Real AI model integration"): the task specifies AdaFace,
but AdaFace's official pretrained checkpoints are distributed via Google
Drive (https://github.com/mk-minchul/AdaFace) or Hugging Face Hub, neither
of which is reachable from this sandbox's network egress. What IS reachable
and genuinely real is a pretrained ArcFace (ResNet/MobileFaceNet backbone,
InsightFace "buffalo" pack) ONNX export hosted on GitHub Releases. ArcFace
and AdaFace are both margin-based face recognition losses trained to the
same goal (512-d embeddings compared by cosine similarity) - AdaFace adds
image-quality-adaptive margin on top of the same underlying architecture
family. This module is written against that shared contract
(112x112 aligned input -> 512-d embedding -> cosine similarity), so
dropping in a real AdaFace ONNX export later - once one is obtained by a
network that CAN reach Drive/HuggingFace - requires no code changes, only
pointing ADAFACE_MODEL_PATH at the new file.
"""

from __future__ import annotations

import cv2
import numpy as np
import onnxruntime as ort

from app.ml.align import align_face


class FaceEmbedder:
    INPUT_SIZE = 112

    def __init__(self, model_path: str, providers: list[str]):
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.embedding_dim = self.session.get_outputs()[0].shape[-1]

    def extract(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """
        image: BGR, HxWx3, uint8 (the full frame, not a pre-cropped face).
        landmarks: (5, 2) from SCRFDDetector - used to align the face to the
        canonical 112x112 pose before embedding, exactly as at enrollment
        time (Step 4: identical preprocessing both times).
        """
        aligned = align_face(image, landmarks, output_size=self.INPUT_SIZE)
        blob = cv2.dnn.blobFromImage(
            aligned, 1.0 / 127.5, (self.INPUT_SIZE, self.INPUT_SIZE), (127.5, 127.5, 127.5), swapRB=True,
        )
        embedding = self.session.run(self.output_names, {self.input_name: blob})[0]
        return embedding.flatten().astype(np.float32)
