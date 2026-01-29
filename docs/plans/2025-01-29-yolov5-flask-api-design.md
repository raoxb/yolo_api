# YOLOv5 Flask REST API 服务设计文档

## 概述

将 YOLOv5 训练的图片识别模型（best.pt）封装为 Flask REST API 服务，支持高并发生产环境部署。

## 需求

- **环境**: 生产环境，仅 CPU，高并发（50+ QPS）
- **API**: 接收 Base64 图片，返回检测结果 JSON
- **认证**: API Key 认证
- **日志**: SQLite 数据库存储
- **检测类别**: close_button, action_button
- **Web 界面**: 上传测试、日志查看、仪表板统计

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Nginx (反向代理)                          │
│                    负载均衡 + 静态资源 + SSL                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Gunicorn (多 Worker)                          │
│              多进程处理请求，每个 Worker 独立加载模型               │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Application                           │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   REST API      │   Web 界面       │   后台服务                   │
│  /api/detect    │  /              │   日志写入                   │
│  (API Key 认证)  │  /logs          │   统计计算                   │
│                 │  /dashboard     │                             │
└─────────────────┴─────────────────┴─────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SQLite 数据库                             │
│              detection_logs 表 (请求记录 + 检测结果)              │
└─────────────────────────────────────────────────────────────────┘
```

## API 设计

### POST /api/detect

**请求:**
```
Headers: X-API-Key: your-api-key
Body: {"image": "base64编码的图片"}
```

**响应:**
```json
{
  "detections": [
    {"box": [222, 0, 16, 14], "class": "close_button", "confidence": 0.88},
    {"box": [94, 380, 51, 14], "class": "action_button", "confidence": 0.85}
  ],
  "process_time": 0.876
}
```

## 数据库设计

```sql
CREATE TABLE detection_logs (
    id INTEGER PRIMARY KEY,
    request_time DATETIME,
    process_time FLOAT,
    image_hash TEXT,
    detections JSON,
    client_ip TEXT,
    api_key TEXT
);
```

## 项目结构

```
yolo_api/
├── app.py                 # Flask 应用入口
├── config.py              # 配置
├── gunicorn.conf.py       # Gunicorn 配置
├── requirements.txt       # 依赖
├── models/
│   └── detector.py        # YOLOv5 模型封装
├── api/
│   └── routes.py          # REST API 路由
├── web/
│   └── routes.py          # Web 界面路由
├── services/
│   ├── detection.py       # 检测服务
│   └── logger.py          # 日志服务
├── database/
│   ├── models.py          # SQLAlchemy 模型
│   └── init_db.py         # 数据库初始化
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── index.html
│   ├── logs.html
│   └── dashboard.html
└── best.pt
```

## 高并发策略

| 层级 | 处理方式 |
|------|----------|
| Nginx | 配置 limit_req 做平滑限流 |
| Gunicorn | workers = (cpu_count * 2) + 1, timeout=30 |
| Flask | 专注业务逻辑，不做限流 |

## 技术选型

- Flask 3.x
- Gunicorn
- PyTorch (CPU) + YOLOv5
- Flask-SQLAlchemy + SQLite
- Chart.js
- Pillow + OpenCV
