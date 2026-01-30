from functools import wraps
from flask import Blueprint, request, jsonify, current_app
import logging

from services.detection import DetectionService
from services.logger import LoggerService

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def require_api_key(f):
    """API Key 认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'Missing API Key'}), 401

        if api_key not in current_app.config['API_KEYS']:
            return jsonify({'error': 'Invalid API Key'}), 401

        # 将 API Key 存入 request 上下文
        request.api_key = api_key
        return f(*args, **kwargs)

    return decorated


def get_client_ip():
    """获取客户端真实 IP"""
    # 优先从反向代理头获取
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr


@api_bp.route('/aapi', methods=['POST'])
@require_api_key
def detect():
    """
    目标检测 API

    Request:
        Headers:
            X-API-Key: your-api-key
        Body:
            {"image": "base64编码的图片"}

    Response:
        {
            "detections": [
                {"box": [x, y, w, h], "class": "class_name", "confidence": 0.95}
            ],
            "process_time": 0.123
        }
    """
    try:
        # 解析请求
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400

        if 'img' not in data:
            return jsonify({'error': 'Missing "image" field'}), 400

        base64_image = data['img']

        # 检查图片大小
        max_size = current_app.config.get('MAX_IMAGE_SIZE', 10 * 1024 * 1024)
        if len(base64_image) > max_size:
            return jsonify({'error': f'Image too large. Max size: {max_size} bytes'}), 400

        # 执行检测
        result = DetectionService.detect(base64_image)

        # 记录日志
        LoggerService.log_detection(
            process_time=result['process_time'],
            image_hash=result['image_hash'],
            detections=result['detections'],
            client_ip=get_client_ip(),
            api_key=getattr(request, 'api_key', None),
            status='success'
        )

        return jsonify({
            'detections': result['detections'],
            'process_time': result['process_time']
        })

    except ValueError as e:
        # 图片解码错误
        logger.warning(f"Invalid image: {e}")
        LoggerService.log_detection(
            process_time=0,
            image_hash=None,
            detections=None,
            client_ip=get_client_ip(),
            api_key=getattr(request, 'api_key', None),
            status='error',
            error_message=str(e)
        )
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        # 其他错误
        logger.error(f"Detection error: {e}", exc_info=True)
        LoggerService.log_detection(
            process_time=0,
            image_hash=None,
            detections=None,
            client_ip=get_client_ip(),
            api_key=getattr(request, 'api_key', None),
            status='error',
            error_message=str(e)
        )
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/health', methods=['GET'])
def health():
    """健康检查接口"""
    return jsonify({'status': 'ok'})
