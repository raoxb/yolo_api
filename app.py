import logging
import os
from pathlib import Path
from flask import Flask

from config import Config
from database.models import db
from api.routes import api_bp
from web.routes import web_bp


def init_model(app):
    """初始化模型（自动选择 ONNX 或 PyTorch）"""
    use_onnx = app.config.get('USE_ONNX', 'auto')
    onnx_path = app.config.get('ONNX_MODEL_PATH')
    pt_path = app.config.get('MODEL_PATH')
    confidence = app.config.get('CONFIDENCE_THRESHOLD', 0.25)
    iou = app.config.get('IOU_THRESHOLD', 0.45)

    # 自动选择：优先 ONNX
    if use_onnx == 'auto':
        use_onnx = Path(onnx_path).exists()
    else:
        use_onnx = use_onnx.lower() == 'true'

    if use_onnx and Path(onnx_path).exists():
        from yolo_wrapper.onnx_detector import ONNXDetector
        from yolo_wrapper import detector as det_module

        logging.info(f"Using ONNX Runtime with model: {onnx_path}")
        detector = ONNXDetector(onnx_path, confidence, iou)
        detector.load()
        det_module._detector = detector
    else:
        from yolo_wrapper.detector import init_detector
        logging.info(f"Using PyTorch with model: {pt_path}")
        init_detector(pt_path, confidence, iou)


def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 初始化数据库
    db.init_app(app)

    with app.app_context():
        # 创建表（使用 checkfirst 避免多 worker 竞争）
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table('detection_logs'):
            db.create_all()

        # 启用 SQLite WAL 模式
        try:
            db.session.execute(db.text("PRAGMA journal_mode=WAL"))
            db.session.commit()
        except Exception as e:
            logging.warning(f"Failed to enable WAL mode: {e}")

    # 初始化模型
    init_model(app)

    # 注册蓝图
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    return app


# 创建应用实例（供 Gunicorn 使用）
app = create_app()


if __name__ == '__main__':
    # 开发模式
    app.run(host='0.0.0.0', port=8080, debug=True)
