"""
One-time conversion: the official MiniFASNetV2 checkpoint (PyTorch .pth,
from minivision-ai/Silent-Face-Anti-Spoofing, Apache 2.0) -> ONNX, so the
running application only needs ONNX Runtime (no PyTorch, no CUDA
libraries) for inference. See backend/README.md "Real AI model
integration" for the full download+convert flow.

Requires torch temporarily (not a runtime dependency of the app - see
requirements-dev.txt). This is exactly how the real MiniFASNetV2 weights
CoreSight ships with were produced.

Usage:
    cd backend
    pip install -r requirements-dev.txt
    bash scripts/download_model_weights.sh   # fetches the .pth checkpoint
    python scripts/convert_minifas_to_onnx.py \
        --checkpoint models/2.7_80x80_MiniFASNetV2.pth \
        --output models/minifasnet_v2.onnx
"""

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch  # noqa: E402
from _minifasnet_arch import MiniFASNetV2  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, help="Path to the official .pth checkpoint")
    parser.add_argument("--output", required=True, help="Path to write the .onnx file")
    args = parser.parse_args()

    # conv6_kernel=(5,5) matches get_kernel(80, 80) = ((80+15)//16, (80+15)//16)
    # from the original repo's src/utility.py - the 80x80 input size is
    # baked into this checkpoint's filename and architecture.
    model = MiniFASNetV2(conv6_kernel=(5, 5))

    state_dict = torch.load(args.checkpoint, map_location="cpu")
    first_key = next(iter(state_dict))
    if first_key.startswith("module."):
        # Checkpoint was saved from a DataParallel-wrapped model.
        state_dict = OrderedDict((k[7:], v) for k, v in state_dict.items())
    model.load_state_dict(state_dict)
    model.eval()

    dummy = torch.randn(1, 3, 80, 80)
    torch.onnx.export(
        model, dummy, args.output,
        input_names=["input"], output_names=["output"],
        opset_version=13,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
