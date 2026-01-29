from flask import Blueprint, render_template, request, jsonify
import logging

from services.detection import DetectionService
from services.logger import LoggerService

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """首页 - 上传图片检测"""
    return render_template('index.html')


@web_bp.route('/detect', methods=['POST'])
def web_detect():
    """Web 界面检测接口（不需要 API Key）"""
    try:
        data = request.get_json()

        if not data or 'image' not in data:
            return jsonify({'error': 'Missing image'}), 400

        base64_image = data['image']

        # 执行检测
        result = DetectionService.detect(base64_image)

        # 绘制检测结果
        annotated_image = DetectionService.draw_detections(
            base64_image,
            result['detections']
        )

        # 记录日志
        LoggerService.log_detection(
            process_time=result['process_time'],
            image_hash=result['image_hash'],
            detections=result['detections'],
            client_ip=request.remote_addr,
            api_key='web-interface',
            status='success'
        )

        return jsonify({
            'detections': result['detections'],
            'process_time': result['process_time'],
            'annotated_image': f"data:image/jpeg;base64,{annotated_image}"
        })

    except ValueError as e:
        logger.warning(f"Invalid image: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.error(f"Detection error: {e}", exc_info=True)
        return jsonify({'error': 'Detection failed'}), 500


@web_bp.route('/logs')
def logs():
    """日志查看页"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', None)

    pagination = LoggerService.get_logs(page=page, per_page=20, status=status)

    return render_template('logs.html', pagination=pagination, current_status=status)


@web_bp.route('/dashboard')
def dashboard():
    """仪表板页"""
    stats = LoggerService.get_statistics(days=7)
    return render_template('dashboard.html', stats=stats)


@web_bp.route('/api/stats')
def api_stats():
    """统计数据 API（供仪表板 AJAX 调用）"""
    days = request.args.get('days', 7, type=int)
    stats = LoggerService.get_statistics(days=days)
    return jsonify(stats)
