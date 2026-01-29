import logging
from flask import Flask

from config import Config
from database.models import db
from yolo_wrapper.detector import init_detector
from api.routes import api_bp
from web.routes import web_bp


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
        # 创建表
        db.create_all()

        # 启用 SQLite WAL 模式
        try:
            db.session.execute(db.text("PRAGMA journal_mode=WAL"))
            db.session.commit()
        except Exception as e:
            logging.warning(f"Failed to enable WAL mode: {e}")

    # 初始化模型
    init_detector(
        model_path=app.config['MODEL_PATH'],
        confidence=app.config.get('CONFIDENCE_THRESHOLD', 0.25),
        iou=app.config.get('IOU_THRESHOLD', 0.45)
    )

    # 注册蓝图
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    return app


# 创建应用实例（供 Gunicorn 使用）
app = create_app()


if __name__ == '__main__':
    # 开发模式
    app.run(host='0.0.0.0', port=8080, debug=True)
