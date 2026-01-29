import torch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class YOLODetector:
    """YOLOv5 模型封装"""

    def __init__(self, model_path: str, confidence: float = 0.25, iou: float = 0.45):
        self.model_path = model_path
        self.confidence = confidence
        self.iou = iou
        self.model = None
        self.class_names = []

    def load(self):
        """加载模型"""
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        logger.info(f"Loading YOLOv5 model from {self.model_path}")

        # 使用 ultralytics YOLO 加载自定义模型
        self.model = torch.hub.load(
            'ultralytics/yolov5',
            'custom',
            path=self.model_path,
            force_reload=False,
            trust_repo=True
        )

        # 设置为评估模式
        self.model.eval()

        # 配置推理参数
        self.model.conf = self.confidence
        self.model.iou = self.iou

        # CPU 优化：限制线程数避免 Worker 间争抢
        torch.set_num_threads(1)

        # 获取类别名称
        self.class_names = self.model.names

        logger.info(f"Model loaded successfully. Classes: {self.class_names}")

    # 每个类别保留的最大检测数量
    CLASS_MAX_DETECTIONS = {
        'close_button': 1,   # 只保留置信度最高的 1 个
        'action_button': 2,  # 只保留置信度最高的 2 个
    }
    DEFAULT_MAX_DETECTIONS = 10  # 其他类别默认保留数量

    def detect(self, image):
        """
        执行目标检测

        Args:
            image: PIL Image 或 numpy array

        Returns:
            list: 检测结果列表（按类别过滤后）
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # 执行推理
        results = self.model(image)

        # 解析结果，按类别分组
        detections_by_class = {}
        for *box, conf, cls_id in results.xyxy[0].cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            cls_name = self.class_names[int(cls_id)]
            detection = {
                'box': [x1, y1, x2 - x1, y2 - y1],  # [x, y, width, height]
                'class': cls_name,
                'confidence': float(conf)
            }

            if cls_name not in detections_by_class:
                detections_by_class[cls_name] = []
            detections_by_class[cls_name].append(detection)

        # 按置信度排序并过滤每个类别
        filtered_detections = []
        for cls_name, dets in detections_by_class.items():
            # 按置信度降序排序
            dets.sort(key=lambda x: x['confidence'], reverse=True)
            # 获取该类别的最大保留数量
            max_count = self.CLASS_MAX_DETECTIONS.get(cls_name, self.DEFAULT_MAX_DETECTIONS)
            # 只保留前 N 个
            filtered_detections.extend(dets[:max_count])

        return filtered_detections

    def get_class_names(self):
        """获取模型支持的类别名称"""
        return list(self.class_names.values()) if isinstance(self.class_names, dict) else list(self.class_names)


# 全局模型实例（每个 Worker 进程独立）
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
