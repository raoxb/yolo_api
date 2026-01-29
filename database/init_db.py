from database.models import db


def init_database(app):
    """初始化数据库"""
    with app.app_context():
        # 启用 WAL 模式提升并发性能
        db.engine.execute("PRAGMA journal_mode=WAL")
        db.create_all()
