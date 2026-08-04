"""Extension singletons.

Instantiated bare here and bound to an app inside the factory, so the objects
can be imported anywhere without creating an import cycle back to ``app``.
"""

from __future__ import annotations

import redis
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.models.base import Base

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
cache = Cache()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

# Raw Redis handle for anything that isn't caching: counters, locks, queues,
# pub/sub. Bound in `init_redis()` because the URL comes from config.
redis_client: redis.Redis = redis.Redis()


def init_redis(url: str) -> redis.Redis:
    """(Re)build the shared Redis client from a connection URL."""
    global redis_client
    redis_client = redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30,
        retry_on_timeout=True,
    )
    return redis_client
