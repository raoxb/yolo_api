# YOLOv5 Flask API 生产环境部署指南

## 1. 服务器准备

### 系统要求
- Ubuntu 20.04+ / CentOS 7+
- Python 3.9+
- 建议配置：8核 CPU、16GB 内存

### 安装依赖
```bash
# Ubuntu
sudo apt update
sudo apt install python3-pip python3-venv nginx supervisor -y

# CentOS
sudo yum install python3-pip python3-venv nginx supervisor -y
```

## 2. 部署应用

### 创建应用目录
```bash
sudo mkdir -p /opt/yolo-api
sudo chown $USER:$USER /opt/yolo-api
cd /opt/yolo-api
```

### 上传代码和模型
```bash
# 将项目文件上传到 /opt/yolo-api/
# 确保 best.pt 模型文件在目录中
```

### 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 创建环境变量文件
```bash
cp .env.example .env
# 编辑 .env 设置生产环境配置
vim .env
```

## 3. 启动服务

### 使用 Supervisor 管理进程

服务配置已在 `/etc/supervisor/conf.d/yolo-api.conf`

```bash
# 加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start yolo-api

# 查看状态
sudo supervisorctl status yolo-api
```

### 常用命令
```bash
# 重启
sudo supervisorctl restart yolo-api

# 停止
sudo supervisorctl stop yolo-api

# 查看日志
tail -f /var/log/yolo-api/error.log
```

## 4. 配置 Nginx

Nginx 配置已在 `/etc/nginx/sites-available/yolo-api`

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/yolo-api /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

## 5. 配置 HTTPS (推荐)

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

## 6. 防火墙配置

```bash
# 开放端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 7. 验证部署

```bash
# 健康检查
curl http://localhost/api/health

# 测试 API
curl -X POST http://localhost/api/detect \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-production-key" \
  -d '{"image": "base64_image_data"}'
```

## 8. 监控和日志

### 日志位置
- 应用日志: `/var/log/yolo-api/`
- Nginx 日志: `/var/log/nginx/yolo-api-*.log`

### 查看实时日志
```bash
tail -f /var/log/yolo-api/error.log
tail -f /var/log/nginx/yolo-api-access.log
```

## 9. 性能调优

### 根据 CPU 核心数调整 Worker
编辑 `gunicorn.conf.py`:
```python
workers = (cpu_count * 2) + 1  # 8核 = 17 workers
```

### Nginx 限流配置
已在 nginx 配置中设置:
- 每 IP 每秒 10 个请求
- 突发允许 20 个排队
