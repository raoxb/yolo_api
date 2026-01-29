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
    INPUT_SIZE = 640  # 与 detector 保持一致

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
        orig_w, orig_h = image.size

        # 获取检测器并执行检测
        detector = get_detector()
        detections = detector.detect(image)

        # 将检测结果坐标从 640x640 映射回原始图片尺寸
        target_size = DetectionService.INPUT_SIZE
        scale = min(target_size / orig_w, target_size / orig_h)
        paste_x = (target_size - int(orig_w * scale)) // 2
        paste_y = (target_size - int(orig_h * scale)) // 2

        mapped_detections = []
        for det in detections:
            x, y, w, h = det['box']
            # 减去偏移，除以缩放比例
            orig_x = int((x - paste_x) / scale)
            orig_y = int((y - paste_y) / scale)
            orig_w_box = int(w / scale)
            orig_h_box = int(h / scale)

            # 确保坐标不越界
            orig_x = max(0, orig_x)
            orig_y = max(0, orig_y)

            mapped_detections.append({
                'box': [orig_x, orig_y, orig_w_box, orig_h_box],
                'class': det['class'],
                'confidence': det['confidence']
            })

        process_time = time.time() - start_time

        return {
            'detections': mapped_detections,
            'process_time': round(process_time, 4),
            'image_hash': DetectionService.calculate_image_hash(base64_image)
        }

    @staticmethod
    def draw_detections(base64_image: str, detections: list) -> str:
        """
        在图片上绘制检测结果

        Args:
            base64_image: Base64 编码的原图
            detections: 检测结果列表（已映射到原始坐标）

        Returns:
            str: Base64 编码的标注后图片
        """
        # 解码图片
        image = DetectionService.decode_base64_image(base64_image)
        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        img_h, img_w = img_bgr.shape[:2]

        # 根据图片大小调整线宽
        thickness = max(2, int(min(img_w, img_h) / 200))

        # 绘制检测框（只绘制框，不绘制文字）
        for det in detections:
            x, y, w, h = det['box']
            cls_name = det['class']

            # 确保坐标在图片范围内
            x = max(0, min(x, img_w - 1))
            y = max(0, min(y, img_h - 1))
            w = min(w, img_w - x)
            h = min(h, img_h - y)

            # 获取颜色
            color = DetectionService.COLORS.get(cls_name, DetectionService.DEFAULT_COLOR)

            # 绘制矩形框
            cv2.rectangle(img_bgr, (x, y), (x + w, y + h), color, thickness)

        # 转换回 RGB 并编码为 Base64
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)

        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode('utf-8')
