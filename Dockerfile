FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（opencv-python-headless 需要的库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用约束文件强制使用 headless 版本
RUN echo "opencv-python-headless" > /tmp/constraints.txt && \
    pip install --no-cache-dir -r requirements.txt \
    --constraint /tmp/constraints.txt \
    --extra-index-url https://pypi.org/simple/ && \
    pip uninstall -y opencv-python 2>/dev/null || true && \
    pip list | grep -i opencv

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/problem_images

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
