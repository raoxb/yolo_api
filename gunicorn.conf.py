import multiprocessing

# Worker 配置
# CPU 密集型任务（模型推理），Worker 数量 = CPU 核心数
workers = multiprocessing.cpu_count()
worker_class = 'sync'
timeout = 120  # 模型加载需要时间，增加超时

# 绑定地址
bind = '0.0.0.0:8080'

# 不预加载应用！让每个 Worker 独立加载模型，避免 PyTorch fork 问题
preload_app = False

# 日志
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# 进程名
proc_name = 'yolov5-api'

# 优雅重启
graceful_timeout = 30

# 请求限制
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190


def post_fork(server, worker):
    """Worker 启动后的钩子，用于独立初始化"""
    import torch
    # 确保每个 Worker 使用独立的线程
    torch.set_num_threads(1)
