import os 

bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = 120
graceful_timeout = 30
keepAlive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"