FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 1. 先安装所有依赖
# 2. 卸载所有 opencv 版本
# 3. 重新安装 headless 版本
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless 2>/dev/null; \
    pip install --no-cache-dir opencv-python-headless && \
    python -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/problem_images

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
