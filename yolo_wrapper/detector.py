import torch
import logging
from pathlib import Path
from PIL import Image

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class YOLODetector(BaseDetector):
    """YOLOv5 PyTorch 模型封装"""

    def __init__(self, model_path: str, confidence: float = 0.25, iou: float = 0.45):
        super().__init__(model_path, confidence, iou)
        self.model = None

    def load(self):
        """加载模型"""
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        self.device = 'cpu'
        torch.set_num_threads(1)
        logger.info("Using CPU for inference")

        logger.info(f"Loading YOLOv5 model from {self.model_path}")

        self.model = torch.hub.load(
            'ultralytics/yolov5',
            'custom',
            path=self.model_path,
            force_reload=False,
            trust_repo=True,
            device=self.device
        )

        self.model.eval()
        self.model.conf = self.confidence
        self.model.iou = self.iou
        self.class_names = self.model.names

        logger.info(f"Model loaded successfully on {self.device}. Classes: {self.class_names}")

    def _inference(self, image: Image.Image) -> dict:
        """执行推理"""
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        results = self.model(image)

        detections_by_class = {}
        for *box, conf, cls_id in results.xyxy[0].cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            cls_name = self.class_names[int(cls_id)]
            detection = {
                'box': [x1, y1, x2 - x1, y2 - y1],
                'class': cls_name,
                'confidence': float(conf)
            }

            if cls_name not in detections_by_class:
                detections_by_class[cls_name] = []
            detections_by_class[cls_name].append(detection)

        return detections_by_class


# 全局模型实例
_detector = None


def get_detector():
    """获取全局模型实例"""
    global _detector
    return _detector


def init_detector(model_path: str, confidence: float = 0.25, iou: float = 0.45):
    """初始化全局模型实例"""
    global _detector
    _detector = YOLODetector(model_path, confidence, iou)
    _detector.load()
    return _detector
