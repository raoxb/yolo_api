"""
FastAPI 版本的 YOLOv5 API 服务

启动方式:
    # 开发模式
    uvicorn app_fastapi:app --host 0.0.0.0 --port 8080 --reload

    # 生产模式 (多 Worker)
    uvicorn app_fastapi:app --host 0.0.0.0 --port 8080 --workers 12

    # 或使用 gunicorn + uvicorn worker
    gunicorn app_fastapi:app -w 12 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080
"""

import os
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import Config
from services.detection import DetectionService
from services.logger import LoggerService
from database.models import db, DetectionLog

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ Pydantic 模型 ============

class DetectionRequest(BaseModel):
    """检测请求"""
    image: str = Field(..., description="Base64 编码的图片")


class DetectionBox(BaseModel):
    """检测框"""
    box: List[int] = Field(..., description="[x, y, width, height]")
    class_: str = Field(..., alias="class", description="类别名称")
    confidence: float = Field(..., description="置信度")

    class Config:
        populate_by_name = True


class DetectionResponse(BaseModel):
    """检测响应"""
    detections: List[DetectionBox]
    process_time: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"


class StatsResponse(BaseModel):
    """统计响应"""
    total_requests: int
    success_requests: int
    success_rate: float
    avg_process_time: float
    today_requests: int
    daily_stats: List[dict]
    class_counts: dict


# ============ 全局变量 ============

detector = None
flask_app = None  # 用于数据库操作


def init_detector():
    """初始化检测器"""
    global detector
    from yolo_wrapper import detector as det_module
    import numpy as np
    from PIL import Image

    use_onnx = Config.USE_ONNX
    onnx_path = Config.ONNX_MODEL_PATH
    pt_path = Config.MODEL_PATH
    confidence = Config.CONFIDENCE_THRESHOLD
    iou = Config.IOU_THRESHOLD

    # 自动选择
    if use_onnx == 'auto':
        use_onnx = Path(onnx_path).exists()
    else:
        use_onnx = use_onnx.lower() == 'true'

    if use_onnx and Path(onnx_path).exists():
        from yolo_wrapper.onnx_detector import ONNXDetector
        logger.info(f"Using ONNX Runtime: {onnx_path}")
        detector = ONNXDetector(onnx_path, confidence, iou)
        detector.load()
        # 同时设置到 detector 模块，供 DetectionService 使用
        det_module._detector = detector
    else:
        from yolo_wrapper.detector import YOLODetector
        logger.info(f"Using PyTorch: {pt_path}")
        detector = YOLODetector(pt_path, confidence, iou)
        detector.load()
        det_module._detector = detector

    # 预热：首次推理触发 CoreML/ONNX 编译
    logger.info("Warming up model (first inference)...")
    dummy_image = Image.new('RGB', (640, 640), (128, 128, 128))
    _ = detector.detect(dummy_image)
    logger.info("Model warmup complete")


def init_database():
    """初始化数据库（使用 Flask-SQLAlchemy）"""
    global flask_app
    from flask import Flask

    flask_app = Flask(__name__)
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(flask_app)

    with flask_app.app_context():
        db.create_all()
        try:
            db.session.execute(db.text("PRAGMA journal_mode=WAL"))
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to enable WAL mode: {e}")


# ============ 生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting FastAPI application...")
    init_database()
    init_detector()
    logger.info("Application started successfully")

    yield

    # 关闭时
    logger.info("Shutting down...")


# ============ FastAPI 应用 ============

app = FastAPI(
    title="YOLOv5 Detection API",
    description="YOLOv5 目标检测 REST API 服务",
    version="1.0.0",
    lifespan=lifespan
)

# 静态文件和模板
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ============ 依赖项 ============

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API Key 验证"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    if x_api_key not in Config.API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


# ============ API 路由 ============

@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.post("/api/detect", response_model=DetectionResponse, tags=["Detection"])
async def detect(
    request: Request,
    body: DetectionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    目标检测 API

    - **image**: Base64 编码的图片
    - **X-API-Key**: API 密钥（Header）
    """
    try:
        # 检查图片大小
        if len(body.image) > Config.MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Image too large. Max size: {Config.MAX_IMAGE_SIZE} bytes"
            )

        # 执行检测
        result = DetectionService.detect(body.image)

        # 记录日志
        with flask_app.app_context():
            LoggerService.log_detection(
                process_time=result['process_time'],
                image_hash=result['image_hash'],
                detections=result['detections'],
                client_ip=get_client_ip(request),
                api_key=api_key,
                status='success'
            )

        return {
            "detections": result['detections'],
            "process_time": result['process_time']
        }

    except ValueError as e:
        with flask_app.app_context():
            LoggerService.log_detection(
                process_time=0,
                image_hash=None,
                detections=None,
                client_ip=get_client_ip(request),
                api_key=api_key,
                status='error',
                error_message=str(e)
            )
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_stats(days: int = 7):
    """获取统计数据"""
    with flask_app.app_context():
        stats = LoggerService.get_statistics(days=days)
    return stats


# ============ Web 路由 ============

@app.get("/", response_class=HTMLResponse, tags=["Web"])
async def index(request: Request):
    """首页 - 上传检测"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/detect", tags=["Web"])
async def web_detect(request: Request):
    """Web 界面检测接口"""
    try:
        data = await request.json()
        base64_image = data.get('image')

        if not base64_image:
            return JSONResponse({"error": "Missing image"}, status_code=400)

        # 执行检测
        result = DetectionService.detect(base64_image)

        # 绘制结果
        annotated_image = DetectionService.draw_detections(
            base64_image,
            result['detections']
        )

        # 记录日志
        with flask_app.app_context():
            LoggerService.log_detection(
                process_time=result['process_time'],
                image_hash=result['image_hash'],
                detections=result['detections'],
                client_ip=get_client_ip(request),
                api_key='web-interface',
                status='success'
            )

        return {
            "detections": result['detections'],
            "process_time": result['process_time'],
            "annotated_image": f"data:image/jpeg;base64,{annotated_image}"
        }

    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Detection error: {e}", exc_info=True)
        return JSONResponse({"error": "Detection failed"}, status_code=500)


@app.get("/logs", response_class=HTMLResponse, tags=["Web"])
async def logs(request: Request, page: int = 1, status: Optional[str] = None):
    """日志查看页"""
    with flask_app.app_context():
        pagination = LoggerService.get_logs(page=page, per_page=20, status=status)
        return templates.TemplateResponse("logs.html", {
            "request": request,
            "pagination": pagination,
            "current_status": status
        })


@app.get("/dashboard", response_class=HTMLResponse, tags=["Web"])
async def dashboard(request: Request):
    """仪表板页"""
    with flask_app.app_context():
        stats = LoggerService.get_statistics(days=7)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats
        })


# ============ 启动入口 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
