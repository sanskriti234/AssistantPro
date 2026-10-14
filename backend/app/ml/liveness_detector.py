"""
MiniFASNetV2 liveness/anti-spoofing via ONNX Runtime.

Model: MiniFASNetV2 (Minivision AI's "Silent-Face-Anti-Spoofing", Apache
2.0, https://github.com/minivision-ai/Silent-Face-Anti-Spoofing). Weights:
the real, official `2.7_80x80_MiniFASNetV2.pth` checkpoint from that repo,
loaded with the vendored architecture (scripts/_minifasnet_arch.py) and
exported to ONNX once (backend/README.md documents the exact conversion)
so production inference only needs ONNX Runtime, not a full PyTorch
install.

Preprocessing is ported EXACTLY from the reference's
`AntiSpoofPredict.predict()`: `transforms.ToTensor()` only - raw BGR
channel order (never swapped to RGB - the model was trained directly on
cv2.imread's native ordering) scaled to [0, 1] by dividing by 255, no mean
subtraction. See backend/README.md "Real AI model integration" for the
calibration caveat still open on this component.

Output is a 3-class softmax: index 1 = genuine live face, indices 0 and 2 =
two different spoof-attack categories (print/replay) - collapsed here into
a single is_live decision, matching how the upstream project itself scores
a single model's prediction (see their test.py: `label = argmax`,
`is_live = (label == 1)`).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort


@dataclass
class LivenessResult:
    is_live: bool
    score: float  # softmax probability of the "live" class
    threshold: float


class MiniFASLivenessDetector:
    INPUT_SIZE = 80
    _LIVE_CLASS_INDEX = 1
    _CROP_SCALE = 2.7  # matches the "2.7_80x80" in the checkpoint's own filename

    def __init__(self, model_path: str, providers: list[str]):
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

    def check(self, image: np.ndarray, bbox: tuple[float, float, float, float], threshold: float) -> LivenessResult:
        """
        image: BGR, HxWx3, uint8 (the full frame).
        bbox: the detected face box (x1, y1, x2, y2) from SCRFDDetector.
        """
        crop = self._crop_with_scale(image, bbox, scale=self._CROP_SCALE)
        # ToTensor()-equivalent only: raw BGR order, /255 scale, no mean subtraction.
        blob = cv2.dnn.blobFromImage(crop, 1.0 / 255.0, (self.INPUT_SIZE, self.INPUT_SIZE), (0, 0, 0), swapRB=False)
        logits = self.session.run(self.output_names, {self.input_name: blob})[0]
        probs = self._softmax(logits[0])
        live_score = float(probs[self._LIVE_CLASS_INDEX])
        return LivenessResult(is_live=live_score >= threshold, score=live_score, threshold=threshold)

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()

    @staticmethod
    def _crop_with_scale(image: np.ndarray, bbox: tuple[float, float, float, float], scale: float) -> np.ndarray:
        """
        Ported exactly from the reference implementation's CropImage._get_new_box:
        clamping shifts the box to stay in-frame while preserving its size
        (rather than truncating it), which matters for matching the model's
        training distribution.
        """
        x1, y1, x2, y2 = bbox
        box_w, box_h = x2 - x1, y2 - y1
        src_h, src_w = image.shape[:2]

        effective_scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, scale)
        new_w, new_h = box_w * effective_scale, box_h * effective_scale
        cx, cy = x1 + box_w / 2, y1 + box_h / 2

        left, top = cx - new_w / 2, cy - new_h / 2
        right, bottom = cx + new_w / 2, cy + new_h / 2

        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > src_w - 1:
            left -= right - src_w + 1
            right = src_w - 1
        if bottom > src_h - 1:
            top -= bottom - src_h + 1
            bottom = src_h - 1

        return image[int(top):int(bottom) + 1, int(left):int(right) + 1]
