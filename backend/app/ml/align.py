"""
Shared geometry helpers used by scrfd_detector.py and face_embedder.py.

These implement the standard, publicly documented SCRFD anchor-decoding and
ArcFace 5-point face-alignment algorithms (as described in the SCRFD paper,
https://arxiv.org/abs/2105.04714, and used throughout the InsightFace
ecosystem) - not vendored from any single project, but the well-known
reference implementation of the published math.
"""

from __future__ import annotations

import cv2
import numpy as np
from skimage.transform import SimilarityTransform

# Standard ArcFace 112x112 reference landmark positions (5-point: both eyes,
# nose tip, both mouth corners). Any SCRFD-family detector's keypoints align
# against this same reference, which is why detection and recognition
# models trained independently still compose correctly.
_REFERENCE_LANDMARKS_112 = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """Decodes SCRFD's (left, top, right, bottom) distance predictions into absolute box corners."""
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """Decodes SCRFD's per-keypoint distance predictions into absolute (x, y) keypoint coordinates."""
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def align_face(image: np.ndarray, landmarks: np.ndarray, output_size: int = 112) -> np.ndarray:
    """
    Warps the detected face so its 5 landmarks land on the standard ArcFace
    reference positions, producing the canonical `output_size`x`output_size`
    aligned crop the embedding model expects. Using the same alignment at
    enrollment and recognition time is what makes their embeddings
    comparable (Step 4 requirement: identical preprocessing both times).
    """
    if landmarks.shape != (5, 2):
        raise ValueError(f"Expected 5 landmarks of shape (5,2), got {landmarks.shape}")

    ratio = output_size / 112.0
    reference = _REFERENCE_LANDMARKS_112 * ratio

    transform = SimilarityTransform()
    transform.estimate(landmarks, reference)
    matrix = transform.params[0:2, :]

    return cv2.warpAffine(image, matrix, (output_size, output_size), borderValue=0.0)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel()
    b = b.ravel()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def nms(detections: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy non-max suppression. detections: (N, 5) = [x1, y1, x2, y2, score]."""
    x1, y1, x2, y2, scores = detections.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        overlap = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(overlap <= iou_threshold)[0] + 1]
    return keep
