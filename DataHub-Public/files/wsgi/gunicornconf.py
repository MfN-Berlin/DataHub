import multiprocessing

bind = "0.0.0.0:8060"
workers = int(multiprocessing.cpu_count() * 2)
worker_class = 'gevent'
max_requests = 1000
max_requests_jitter = 50
# Django WSGI application path in pattern MODULE_NAME:VARIABLE_NAME
wsgi_app = "gdm.wsgi:application"
raw_env = "DJANGO_SETTINGS_MODULE=gdm.settings"
# chdir = "/gdm"
loglevel = "debug"
timeout = "3000"
graceful_timeout = "3000"
# default_proc_name = "datahub"
keepalive = 10
# Restart workers when code changes (development only!)
# reload = True
