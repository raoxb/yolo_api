from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class DetectionLog(db.Model):
    """检测日志记录"""
    __tablename__ = 'detection_logs'

    id = db.Column(db.Integer, primary_key=True)
    request_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    process_time = db.Column(db.Float)  # 处理耗时(秒)
    image_hash = db.Column(db.String(64), index=True)  # 图片 MD5 哈希
    detections = db.Column(db.JSON)  # 检测结果
    detection_count = db.Column(db.Integer, default=0)  # 检测到的目标数量
    client_ip = db.Column(db.String(45))  # 支持 IPv6
    api_key = db.Column(db.String(100))  # 使用的 API Key (脱敏存储)
    status = db.Column(db.String(20), default='success')  # success / error
    error_message = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'request_time': self.request_time.isoformat() if self.request_time else None,
            'process_time': self.process_time,
            'image_hash': self.image_hash,
            'detections': self.detections,
            'detection_count': self.detection_count,
            'client_ip': self.client_ip,
            'status': self.status,
            'error_message': self.error_message
        }
