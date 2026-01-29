import os
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from PIL import Image
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """检测器基类 - 包含公共逻辑"""

    # 每个类别保留的最大检测数量
    CLASS_MAX_DETECTIONS = {
        'close_button': 1,
        'action_button': 2,
    }
    DEFAULT_MAX_DETECTIONS = 10
    INPUT_SIZE = 640

    # 需要检测的必须类别
    REQUIRED_CLASSES = ['close_button', 'action_button']
    # 低置信度阈值
    LOW_CONFIDENCE_THRESHOLD = 0.5
    # 保存问题图片的目录
    PROBLEM_IMAGES_DIR = 'problem_images'

    def __init__(self, model_path: str, confidence: float = 0.25, iou: float = 0.45):
        self.model_path = model_path
        self.confidence = confidence
        self.iou = iou
        self.class_names = {}
        self._init_problem_dirs()

    def _init_problem_dirs(self):
        """初始化问题图片保存目录"""
        self.problem_base_dir = Path(self.PROBLEM_IMAGES_DIR)
        self.problem_base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Problem images will be saved to: {self.problem_base_dir.absolute()}")

    def _get_date_dir(self, base_path: Path) -> Path:
        """获取按日期分类的目录"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        date_dir = base_path / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    def _generate_filename(self, image: Image.Image, reason: str) -> str:
        """生成保存的文件名"""
        timestamp = datetime.now().strftime('%H%M%S_%f')
        img_bytes = image.tobytes()[:1000] if hasattr(image, 'tobytes') else b''
        img_hash = hashlib.md5(img_bytes).hexdigest()[:8]
        return f"{timestamp}_{img_hash}_{reason}.jpg"

    def _save_problem_image(self, original_image: Image.Image, detections: list, reason: str, category: str):
        """
        保存问题图片

        Args:
            original_image: 原始 PIL Image
            detections: 检测结果
            reason: 保存原因
            category: 分类目录 (low_confidence / missing_close_button / missing_action_button)
        """
        try:
            if not isinstance(original_image, Image.Image):
                original_image = Image.fromarray(original_image)

            # 按类别和日期创建目录
            category_dir = self.problem_base_dir / category
            save_dir = self._get_date_dir(category_dir)

            filename = self._generate_filename(original_image, reason)
            filepath = save_dir / filename

            # 保存图片
            original_image.save(filepath, 'JPEG', quality=95)

            # 保存检测信息
            info_path = filepath.with_suffix('.txt')
            with open(info_path, 'w') as f:
                f.write(f"Reason: {reason}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write(f"Detections:\n")
                for det in detections:
                    f.write(f"  - {det['class']}: {det['confidence']:.4f} at {det['box']}\n")

            logger.debug(f"Saved problem image: {filepath}")

        except Exception as e:
            logger.warning(f"Failed to save problem image: {e}")

    def _check_and_save_problems(self, original_image: Image.Image, detections: list):
        """检查检测结果并保存问题图片"""
        detected_classes = set(det['class'] for det in detections)
        max_confidence = max((det['confidence'] for det in detections), default=0)

        # 检查缺少的类别，分别保存到不同目录
        for required_class in self.REQUIRED_CLASSES:
            if required_class not in detected_classes:
                self._save_problem_image(
                    original_image,
                    detections,
                    f"missing_{required_class}",
                    f"missing_{required_class}"  # 目录名
                )

        # 检查低置信度
        if detections and max_confidence < self.LOW_CONFIDENCE_THRESHOLD:
            self._save_problem_image(
                original_image,
                detections,
                f"low_conf_{max_confidence:.2f}",
                "low_confidence"  # 目录名
            )

        # 没有任何检测结果
        if not detections:
            self._save_problem_image(
                original_image,
                detections,
                "no_detection",
                "no_detection"  # 目录名
            )

    def _preprocess_image(self, image) -> Image.Image:
        """预处理图片，确保尺寸兼容"""
        if not isinstance(image, Image.Image):
            image = Image.fromarray(image)

        orig_w, orig_h = image.size
        target_size = self.INPUT_SIZE

        # 计算缩放比例
        scale = min(target_size / orig_w, target_size / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # Resize
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 创建 640x640 背景
        new_image = Image.new('RGB', (target_size, target_size), (114, 114, 114))
        paste_x = (target_size - new_w) // 2
        paste_y = (target_size - new_h) // 2
        new_image.paste(resized, (paste_x, paste_y))

        return new_image

    def _filter_detections(self, detections_by_class: dict) -> list:
        """按类别过滤检测结果"""
        filtered_detections = []
        for cls_name, dets in detections_by_class.items():
            dets.sort(key=lambda x: x['confidence'], reverse=True)
            max_count = self.CLASS_MAX_DETECTIONS.get(cls_name, self.DEFAULT_MAX_DETECTIONS)
            filtered_detections.extend(dets[:max_count])
        return filtered_detections

    @abstractmethod
    def load(self):
        """加载模型"""
        pass

    @abstractmethod
    def _inference(self, image: Image.Image) -> list:
        """执行推理，返回原始检测结果"""
        pass

    def detect(self, image) -> list:
        """
        执行目标检测

        Args:
            image: PIL Image 或 numpy array

        Returns:
            list: 检测结果列表
        """
        # 保存原始图片引用
        if not isinstance(image, Image.Image):
            original_image = Image.fromarray(image)
        else:
            original_image = image.copy()

        # 预处理
        processed_image = self._preprocess_image(image)

        # 执行推理
        detections_by_class = self._inference(processed_image)

        # 过滤结果
        filtered_detections = self._filter_detections(detections_by_class)

        # 检查并保存问题图片
        self._check_and_save_problems(original_image, filtered_detections)

        return filtered_detections

    def get_class_names(self) -> list:
        """获取类别名称"""
        if isinstance(self.class_names, dict):
            return list(self.class_names.values())
        return list(self.class_names)
