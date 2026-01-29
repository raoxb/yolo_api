import logging
import numpy as np
from pathlib import Path
from PIL import Image

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class ONNXDetector(BaseDetector):
    """ONNX Runtime 模型封装 - 更快的 CPU 推理"""

    def __init__(self, model_path: str, confidence: float = 0.25, iou: float = 0.45):
        super().__init__(model_path, confidence, iou)
        self.session = None
        self.class_names = {0: 'close_button', 1: 'action_button'}

    def load(self):
        """加载 ONNX 模型"""
        import onnxruntime as ort

        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        logger.info(f"Loading ONNX model from {self.model_path}")

        providers = []
        if 'CoreMLExecutionProvider' in ort.get_available_providers():
            providers.append('CoreMLExecutionProvider')
            logger.info("Using CoreML execution provider (Apple Silicon optimized)")
        providers.append('CPUExecutionProvider')

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 1

        self.session = ort.InferenceSession(
            self.model_path,
            sess_options=sess_options,
            providers=providers
        )

        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

        logger.info(f"ONNX model loaded. Providers: {self.session.get_providers()}")

    def _preprocess_image(self, image) -> np.ndarray:
        """预处理图片为 ONNX 输入格式"""
        # 先调用父类方法获取 PIL Image
        pil_image = super()._preprocess_image(image)

        # 转换为 numpy，归一化，调整维度
        img_array = np.array(pil_image).astype(np.float32) / 255.0
        img_array = img_array.transpose(2, 0, 1)  # HWC -> CHW
        img_array = np.expand_dims(img_array, axis=0)  # 添加 batch 维度

        return img_array

    def _nms(self, boxes, scores, iou_threshold):
        """非极大值抑制"""
        if len(boxes) == 0:
            return []

        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)

        order = scores.argsort()[::-1]
        keep = []

        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            inter = w * h

            iou = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def _inference(self, image) -> dict:
        """执行推理"""
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # 预处理为 numpy 数组
        if isinstance(image, Image.Image):
            input_tensor = self._preprocess_image(image)
        else:
            input_tensor = image

        # 推理
        outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
        output = outputs[0]

        # 解析输出
        detections_by_class = {}

        predictions = output[0] if len(output.shape) == 3 else output

        for pred in predictions:
            if len(pred) < 6:
                continue

            x_center, y_center, w, h = pred[0:4]
            obj_conf = pred[4]
            class_scores = pred[5:]

            class_id = np.argmax(class_scores)
            class_conf = class_scores[class_id]
            confidence = obj_conf * class_conf

            if confidence < self.confidence:
                continue

            x1 = int(x_center - w / 2)
            y1 = int(y_center - h / 2)
            x2 = int(x_center + w / 2)
            y2 = int(y_center + h / 2)

            cls_name = self.class_names.get(int(class_id), f'class_{class_id}')

            detection = {
                'box': [x1, y1, x2 - x1, y2 - y1],
                'class': cls_name,
                'confidence': float(confidence),
                '_x1y1x2y2': [x1, y1, x2, y2]
            }

            if cls_name not in detections_by_class:
                detections_by_class[cls_name] = []
            detections_by_class[cls_name].append(detection)

        # NMS
        for cls_name, dets in detections_by_class.items():
            if not dets:
                continue

            boxes = np.array([d['_x1y1x2y2'] for d in dets])
            scores = np.array([d['confidence'] for d in dets])

            keep_indices = self._nms(boxes, scores, self.iou)
            kept_dets = [dets[i] for i in keep_indices]

            # 移除临时字段
            for det in kept_dets:
                del det['_x1y1x2y2']

            detections_by_class[cls_name] = kept_dets

        return detections_by_class
