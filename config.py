import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()


class Config:
    """应用配置"""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "detection.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 模型配置
    # 优先使用 ONNX 模型（更快），如果不存在则使用 PyTorch 模型
    ONNX_MODEL_PATH = os.environ.get('ONNX_MODEL_PATH', str(BASE_DIR / 'best.onnx'))
    MODEL_PATH = os.environ.get('MODEL_PATH', str(BASE_DIR / 'best.pt'))
    USE_ONNX = os.environ.get('USE_ONNX', 'auto')  # auto / true / false

    # API Keys (生产环境建议从环境变量或数据库读取)
    API_KEYS = os.environ.get('API_KEYS', 'test-api-key-123,another-key-456').split(',')

    # 检测配置
    CONFIDENCE_THRESHOLD = float(os.environ.get('CONFIDENCE_THRESHOLD', '0.25'))
    IOU_THRESHOLD = float(os.environ.get('IOU_THRESHOLD', '0.45'))
    MAX_IMAGE_SIZE = int(os.environ.get('MAX_IMAGE_SIZE', '10485760'))  # 10MB

    # 日志
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
