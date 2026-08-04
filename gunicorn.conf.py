"""Gunicorn configuration for the production container."""

from __future__ import annotations

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically so a slow leak never becomes an outage.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Honour X-Forwarded-* from the reverse proxy in front of the container.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
proxy_protocol = False

preload_app = False  # keep False: each worker opens its own DB pool
