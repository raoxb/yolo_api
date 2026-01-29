import base64
import hashlib
import io
import time
import logging
from PIL import Image
import cv2
import numpy as np

from yolo_wrapper.detector import get_detector

logger = logging.getLogger(__name__)


class DetectionService:
    """检测服务"""

    # 检测框颜色配置（BGR格式）
    COLORS = {
        'close_button': (0, 0, 255),    # 红色
        'action_button': (0, 255, 0),   # 绿色
    }
    DEFAULT_COLOR = (255, 0, 0)  # 蓝色

    @staticmethod
    def decode_base64_image(base64_string: str) -> Image.Image:
        """
        解码 Base64 图片

        Args:
            base64_string: Base64 编码的图片字符串

        Returns:
            PIL Image 对象

        Raises:
            ValueError: 图片解码失败
        """
        try:
            # 处理可能包含的 data URI 前缀
            if ',' in base64_string:
                base64_string = base64_string.split(',', 1)[1]

            image_data = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_data))

            # 转换为 RGB（处理 RGBA 或其他格式）
            if image.mode != 'RGB':
                image = image.convert('RGB')

            return image
        except Exception as e:
            logger.error(f"Failed to decode image: {e}")
            raise ValueError(f"Invalid image data: {e}")

    @staticmethod
    def calculate_image_hash(base64_string: str) -> str:
        """计算图片的 MD5 哈希"""
        if ',' in base64_string:
            base64_string = base64_string.split(',', 1)[1]
        return hashlib.md5(base64_string.encode()).hexdigest()

    @staticmethod
    def detect(base64_image: str) -> dict:
        """
        执行目标检测

        Args:
            base64_image: Base64 编码的图片

        Returns:
            dict: 包含检测结果和处理时间
        """
        start_time = time.time()

        # 解码图片
        image = DetectionService.decode_base64_image(base64_image)

        # 获取检测器并执行检测
        detector = get_detector()
        detections = detector.detect(image)

        process_time = time.time() - start_time

        return {
            'detections': detections,
            'process_time': round(process_time, 4),
            'image_hash': DetectionService.calculate_image_hash(base64_image)
        }

    @staticmethod
    def draw_detections(base64_image: str, detections: list) -> str:
        """
        在图片上绘制检测结果

        Args:
            base64_image: Base64 编码的原图
            detections: 检测结果列表

        Returns:
            str: Base64 编码的标注后图片
        """
        # 解码图片
        image = DetectionService.decode_base64_image(base64_image)
        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # 绘制检测框
        for det in detections:
            x, y, w, h = det['box']
            cls_name = det['class']
            conf = det['confidence']

            # 获取颜色
            color = DetectionService.COLORS.get(cls_name, DetectionService.DEFAULT_COLOR)

            # 绘制矩形框
            cv2.rectangle(img_bgr, (x, y), (x + w, y + h), color, 2)

            # 绘制标签背景
            label = f"{cls_name}: {conf:.2f}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                img_bgr,
                (x, y - label_h - baseline - 5),
                (x + label_w, y),
                color,
                -1
            )

            # 绘制标签文字
            cv2.putText(
                img_bgr,
                label,
                (x, y - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        # 转换回 RGB 并编码为 Base64
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)

        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode('utf-8')
