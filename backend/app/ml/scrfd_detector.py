"""
SCRFD face detection via ONNX Runtime.

Model: SCRFD (Sample and Computation Redistribution for Efficient Face
Detection), https://arxiv.org/abs/2105.04714. Weights: real, pretrained
SCRFD-500MF ONNX export from the InsightFace "buffalo" model pack (see
backend/README.md "Real AI model integration" for exact provenance and the
download script - these are the standard, widely-deployed InsightFace
detector weights, not placeholders).

Returns real bounding boxes, confidence scores, and 5-point landmarks for
every face found - 0, 1, or several. Callers decide what "0" or "several"
means for their use case (this module never picks a face for you).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

from app.ml.align import distance2bbox, distance2kps, nms


@dataclass
class FaceDetection:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    score: float
    landmarks: np.ndarray  # shape (5, 2)


class SCRFDDetector:
    _FEAT_STRIDE_FPN = (8, 16, 32)
    _NUM_ANCHORS = 2
    _MEAN = 127.5
    _STD = 128.0

    def __init__(self, model_path: str, providers: list[str], input_size: tuple[int, int] = (640, 640)):
        self.input_size = input_size
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self._center_cache: dict[tuple[int, int, int], np.ndarray] = {}

    def detect(self, image: np.ndarray, confidence_threshold: float, iou_threshold: float = 0.4) -> list[FaceDetection]:
        """image: BGR, HxWx3, uint8. Returns every face found above confidence_threshold."""
        width, height = self.input_size
        im_ratio = image.shape[0] / image.shape[1]
        model_ratio = height / width
        if im_ratio > model_ratio:
            new_height, new_width = height, int(height / im_ratio)
        else:
            new_width, new_height = width, int(width * im_ratio)

        det_scale = new_height / image.shape[0]
        resized = cv2.resize(image, (new_width, new_height))
        padded = np.zeros((height, width, 3), dtype=np.uint8)
        padded[:new_height, :new_width, :] = resized

        scores_list, bboxes_list, kpss_list = self._forward(padded, confidence_threshold)
        if not scores_list or all(s.size == 0 for s in scores_list):
            return []

        scores = np.vstack(scores_list)
        order = scores.ravel().argsort()[::-1]
        bboxes = np.vstack(bboxes_list) / det_scale
        kpss = np.vstack(kpss_list) / det_scale

        pre_det = np.hstack((bboxes, scores)).astype(np.float32)[order]
        kpss = kpss[order]
        keep = nms(pre_det, iou_threshold)

        results = []
        for i in keep:
            x1, y1, x2, y2, score = pre_det[i]
            results.append(FaceDetection(bbox=(float(x1), float(y1), float(x2), float(y2)), score=float(score), landmarks=kpss[i]))
        return results

    def _forward(self, padded_image: np.ndarray, threshold: float):
        blob = cv2.dnn.blobFromImage(
            padded_image, 1.0 / self._STD, (padded_image.shape[1], padded_image.shape[0]),
            (self._MEAN, self._MEAN, self._MEAN), swapRB=True,
        )
        outputs = self.session.run(self.output_names, {self.input_name: blob})

        input_h, input_w = blob.shape[2], blob.shape[3]
        fmc = len(self._FEAT_STRIDE_FPN)

        scores_list, bboxes_list, kpss_list = [], [], []
        for idx, stride in enumerate(self._FEAT_STRIDE_FPN):
            scores = outputs[idx]
            bbox_preds = outputs[idx + fmc] * stride
            kps_preds = outputs[idx + fmc * 2] * stride

            h, w = input_h // stride, input_w // stride
            key = (h, w, stride)
            if key in self._center_cache:
                centers = self._center_cache[key]
            else:
                centers = np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32)
                centers = (centers * stride).reshape((-1, 2))
                centers = np.stack([centers] * self._NUM_ANCHORS, axis=1).reshape((-1, 2))
                if len(self._center_cache) < 100:
                    self._center_cache[key] = centers

            pos = np.where(scores.ravel() >= threshold)[0]
            bboxes = distance2bbox(centers, bbox_preds)
            kpss = distance2kps(centers, kps_preds).reshape((-1, 5, 2))

            scores_list.append(scores.reshape(-1, 1)[pos])
            bboxes_list.append(bboxes[pos])
            kpss_list.append(kpss[pos])

        return scores_list, bboxes_list, kpss_list
