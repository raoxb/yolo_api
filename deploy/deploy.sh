#!/bin/bash
set -e

# YOLOv5 API 快速部署脚本
# 使用方法: sudo bash deploy.sh

APP_DIR="/opt/yolo-api"
LOG_DIR="/var/log/yolo-api"
DATA_DIR="${APP_DIR}/data"

echo "=== YOLOv5 API 部署脚本 ==="

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 创建目录
echo "[1/7] 创建目录..."
mkdir -p ${APP_DIR}
mkdir -p ${LOG_DIR}
mkdir -p ${DATA_DIR}

# 2. 复制文件
echo "[2/7] 复制应用文件..."
cp -r ./* ${APP_DIR}/
chown -R www-data:www-data ${APP_DIR}
chown -R www-data:www-data ${LOG_DIR}

# 3. 创建虚拟环境
echo "[3/7] 创建 Python 虚拟环境..."
cd ${APP_DIR}
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 配置环境变量
echo "[4/7] 配置环境变量..."
if [ ! -f ${APP_DIR}/.env ]; then
    cp ${APP_DIR}/.env.example ${APP_DIR}/.env
    # 生成随机密钥
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/your-super-secret-key-change-this-in-production/${SECRET}/" ${APP_DIR}/.env
    echo "已创建 .env 文件，请编辑 ${APP_DIR}/.env 配置 API_KEYS"
fi

# 5. 配置 Supervisor
echo "[5/7] 配置 Supervisor..."
cp ${APP_DIR}/deploy/supervisor/yolo-api.conf /etc/supervisor/conf.d/
supervisorctl reread
supervisorctl update

# 6. 配置 Nginx
echo "[6/7] 配置 Nginx..."
cp ${APP_DIR}/deploy/nginx/yolo-api.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/yolo-api.conf /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# 7. 启动服务
echo "[7/7] 启动服务..."
supervisorctl start yolo-api

echo ""
echo "=== 部署完成 ==="
echo ""
echo "下一步操作:"
echo "1. 编辑 ${APP_DIR}/.env 配置生产环境 API_KEYS"
echo "2. 编辑 /etc/nginx/sites-available/yolo-api.conf 配置域名"
echo "3. 运行 sudo certbot --nginx 配置 HTTPS"
echo ""
echo "查看服务状态: sudo supervisorctl status yolo-api"
echo "查看日志: tail -f ${LOG_DIR}/error.log"
