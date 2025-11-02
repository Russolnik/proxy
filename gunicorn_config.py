# Gunicorn конфигурация для Flask-SocketIO
import multiprocessing
import os

# Количество воркеров
workers = 1  # Flask-SocketIO требует 1 воркер для правильной работы Socket.IO
worker_class = 'gevent'
worker_connections = 1000

# Биндинг
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Таймауты
timeout = 120
keepalive = 5

# Логирование
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Процесс
proc_name = 'websocket-proxy'

# Режим daemon
daemon = False

