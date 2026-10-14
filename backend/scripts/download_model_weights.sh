#!/usr/bin/env bash
# Downloads real, pretrained model weights for CoreSight's face-recognition
# pipeline. See backend/README.md "Real AI model integration" for exact
# provenance, licenses, and why AdaFace's official weights (Google
# Drive/HuggingFace-hosted) are substituted with a real ArcFace ONNX export
# here instead.
#
# Usage: bash scripts/download_model_weights.sh [output_dir]
set -euo pipefail

OUT_DIR="${1:-models}"
mkdir -p "$OUT_DIR"

echo "Downloading SCRFD-500MF detector (InsightFace buffalo pack, ~2.4MB)..."
curl -sL -o "$OUT_DIR/det_500m.onnx" \
  "https://github.com/yakhyo/face-reidentification/releases/download/v0.0.1/det_500m.onnx"

echo "Downloading ArcFace MobileFaceNet recognition model (~13MB)..."
echo "  NOTE: this is the AdaFace substitute - see README 'Real AI model integration'."
curl -sL -o "$OUT_DIR/w600k_mbf.onnx" \
  "https://github.com/yakhyo/face-reidentification/releases/download/v0.0.1/w600k_mbf.onnx"

echo "Downloading official MiniFASNetV2 liveness checkpoint (~1.8MB, .pth)..."
curl -sL -o "$OUT_DIR/2.7_80x80_MiniFASNetV2.pth" \
  "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"

echo ""
echo "Downloaded to $OUT_DIR/:"
ls -la "$OUT_DIR"
echo ""
echo "MiniFASNetV2 must still be converted from .pth to .onnx (one-time, needs torch):"
echo "  pip install -r requirements-dev.txt"
echo "  python scripts/convert_minifas_to_onnx.py \\"
echo "      --checkpoint $OUT_DIR/2.7_80x80_MiniFASNetV2.pth \\"
echo "      --output $OUT_DIR/minifasnet_v2.onnx"
echo ""
echo "Then set in backend/.env:"
echo "  SCRFD_MODEL_PATH=$OUT_DIR/det_500m.onnx"
echo "  ADAFACE_MODEL_PATH=$OUT_DIR/w600k_mbf.onnx"
echo "  MINIFAS_MODEL_PATH=$OUT_DIR/minifasnet_v2.onnx"
