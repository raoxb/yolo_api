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
        from sqlalchemy import func
        from datetime import timedelta

        now = datetime.utcnow()
        start_date = now - timedelta(days=days)

        # 总请求数
        total_requests = DetectionLog.query.filter(
            DetectionLog.request_time >= start_date
        ).count()

        # 成功请求数
        success_requests = DetectionLog.query.filter(
            DetectionLog.request_time >= start_date,
            DetectionLog.status == 'success'
        ).count()

        # 平均处理时间
        avg_time_result = db.session.query(
            func.avg(DetectionLog.process_time)
        ).filter(
            DetectionLog.request_time >= start_date,
            DetectionLog.status == 'success'
        ).scalar()
        avg_process_time = round(float(avg_time_result or 0), 3)

        # 今日请求数
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = DetectionLog.query.filter(
            DetectionLog.request_time >= today_start
        ).count()

        # 每日请求趋势
        daily_stats = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = DetectionLog.query.filter(
                DetectionLog.request_time >= day_start,
                DetectionLog.request_time < day_end
            ).count()
            daily_stats.append({
                'date': day_start.strftime('%m-%d'),
                'count': count
            })

        # 类别分布统计
        class_counts = {'close_button': 0, 'action_button': 0}
        logs = DetectionLog.query.filter(
            DetectionLog.request_time >= start_date,
            DetectionLog.status == 'success'
        ).all()

        for log in logs:
            if log.detections:
                for det in log.detections:
                    cls_name = det.get('class', '')
                    if cls_name in class_counts:
                        class_counts[cls_name] += 1

        return {
            'total_requests': total_requests,
            'success_requests': success_requests,
            'success_rate': round(success_requests / total_requests * 100, 1) if total_requests > 0 else 0,
            'avg_process_time': avg_process_time,
            'today_requests': today_requests,
            'daily_stats': daily_stats,
            'class_counts': class_counts
        }
