import multiprocessing

# Worker 配置
workers = (multiprocessing.cpu_count() * 2) + 1
worker_class = 'sync'
timeout = 30

# 绑定地址
bind = '0.0.0.0:8080'

# 预加载应用
preload_app = True

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
