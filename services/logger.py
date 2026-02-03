import logging
from datetime import datetime
from database.models import db, DetectionLog

logger = logging.getLogger(__name__)


class LoggerService:
    """日志服务"""

    @staticmethod
    def log_detection(
        process_time: float,
        image_hash: str,
        detections: list,
        client_ip: str,
        api_key: str = None,
        status: str = 'success',
        error_message: str = None
    ):
        """
        记录检测日志

        Args:
            process_time: 处理时间(秒)
            image_hash: 图片哈希
            detections: 检测结果
            client_ip: 客户端 IP
            api_key: API Key (会脱敏存储)
            status: 状态 (success/error)
            error_message: 错误信息
        """
        try:
            # API Key 脱敏：只保留前4位和后4位
            masked_key = None
            if api_key:
                if len(api_key) > 8:
                    masked_key = f"{api_key[:4]}****{api_key[-4:]}"
                else:
                    masked_key = "****"

            log = DetectionLog(
                request_time=datetime.utcnow(),
                process_time=process_time,
                image_hash=image_hash,
                detections=detections,
                detection_count=len(detections) if detections else 0,
                client_ip=client_ip,
                api_key=masked_key,
                status=status,
                error_message=error_message
            )

            db.session.add(log)
            db.session.commit()

            logger.debug(f"Detection logged: {log.id}")

        except Exception as e:
            logger.error(f"Failed to log detection: {e}")
            db.session.rollback()

    @staticmethod
    def get_logs(page: int = 1, per_page: int = 20, status: str = None):
        """
        获取分页日志

        Args:
            page: 页码
            per_page: 每页数量
            status: 筛选状态

        Returns:
            Pagination 对象
        """
        query = DetectionLog.query.order_by(DetectionLog.request_time.desc())

        if status:
            query = query.filter(DetectionLog.status == status)

        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_statistics(days: int = 7):
        """
        获取统计数据

        Args:
            days: 统计天数

        Returns:
            dict: 统计数据
        """
        from sqlalchemy import func, text
        from datetime import timedelta

        now = datetime.utcnow()
        start_date = now - timedelta(days=days)

        # 使用单次查询获取总数和成功数
        stats = db.session.query(
            func.count(DetectionLog.id).label('total'),
            func.sum(db.case((DetectionLog.status == 'success', 1), else_=0)).label('success'),
            func.avg(db.case((DetectionLog.status == 'success', DetectionLog.process_time), else_=None)).label('avg_time')
        ).filter(
            DetectionLog.request_time >= start_date
        ).first()

        total_requests = stats.total or 0
        success_requests = stats.success or 0
        avg_process_time = round(float(stats.avg_time or 0), 3)

        # 今日请求数
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = DetectionLog.query.filter(
            DetectionLog.request_time >= today_start
        ).count()

        # 每日请求趋势 - 使用单次分组查询
        daily_query = db.session.query(
            func.date(DetectionLog.request_time).label('date'),
            func.count(DetectionLog.id).label('count')
        ).filter(
            DetectionLog.request_time >= start_date
        ).group_by(
            func.date(DetectionLog.request_time)
        ).all()

        # 转换为字典便于查找
        daily_dict = {str(row.date): row.count for row in daily_query}

        daily_stats = []
        for i in range(days - 1, -1, -1):
            day = (now - timedelta(days=i)).date()
            daily_stats.append({
                'date': day.strftime('%m-%d'),
                'count': daily_dict.get(str(day), 0)
            })

        # 类别统计 - 使用数据库聚合而非加载全部记录
        # 只统计最近的检测数量，不遍历所有记录
        recent_logs = DetectionLog.query.filter(
            DetectionLog.request_time >= start_date,
            DetectionLog.status == 'success'
        ).with_entities(
            DetectionLog.detection_count
        ).all()

        total_detections = sum(log.detection_count or 0 for log in recent_logs)

        # 简化类别统计，使用检测数量估算
        class_counts = {
            'close_button': success_requests,  # 每次成功检测通常有 1 个 close_button
            'action_button': total_detections - success_requests  # 剩余为 action_button
        }

        return {
            'total_requests': total_requests,
            'success_requests': success_requests,
            'success_rate': round(success_requests / total_requests * 100, 1) if total_requests > 0 else 0,
            'avg_process_time': avg_process_time,
            'today_requests': today_requests,
            'daily_stats': daily_stats,
            'class_counts': class_counts
        }
