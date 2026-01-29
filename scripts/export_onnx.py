#!/usr/bin/env python3
"""
将 YOLOv5 PyTorch 模型导出为 ONNX 格式

使用方法:
    python scripts/export_onnx.py --weights best.pt --output best.onnx
"""

import argparse
import subprocess
import sys
from pathlib import Path


def export_onnx(weights_path: str, output_path: str, img_size: int = 640):
    """使用 YOLOv5 官方导出脚本"""
    print(f"Exporting {weights_path} to ONNX format...")

    # 使用 YOLOv5 的 export.py
    yolov5_path = Path.home() / '.cache/torch/hub/ultralytics_yolov5_master'

    if not yolov5_path.exists():
        # 先加载一次模型触发下载
        import torch
        print("Downloading YOLOv5...")
        torch.hub.load('ultralytics/yolov5', 'custom', path=weights_path, force_reload=False, trust_repo=True)

    export_script = yolov5_path / 'export.py'

    if export_script.exists():
        # 使用官方导出脚本
        cmd = [
            sys.executable,
            str(export_script),
            '--weights', weights_path,
            '--img-size', str(img_size),
            '--include', 'onnx',
            '--simplify'
        ]
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False)

        # 官方脚本会生成同名的 .onnx 文件
        generated_onnx = Path(weights_path).with_suffix('.onnx')
        if generated_onnx.exists() and str(generated_onnx) != output_path:
            generated_onnx.rename(output_path)
            print(f"Renamed to: {output_path}")

        if Path(output_path).exists():
            print(f"✅ ONNX model exported: {output_path}")
            print(f"   Size: {Path(output_path).stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("❌ Export failed")
            sys.exit(1)
    else:
        print(f"❌ Export script not found: {export_script}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Export YOLOv5 to ONNX')
    parser.add_argument('--weights', type=str, default='best.pt', help='PyTorch weights path')
    parser.add_argument('--output', type=str, default='best.onnx', help='ONNX output path')
    parser.add_argument('--img-size', type=int, default=640, help='Input image size')

    args = parser.parse_args()
    export_onnx(args.weights, args.output, args.img_size)


if __name__ == '__main__':
    main()
