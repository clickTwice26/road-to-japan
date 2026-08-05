# roadtojapan

A production-shaped Flask API. Application, PostgreSQL and Redis all run in Docker —
nothing needs to be installed on the host except Docker itself.

| Component     | Version | Role |
| ------------- | ------- | ---- |
| Flask         | 3.1.3   | Application factory + blueprints |
| SQLAlchemy    | 2.0.51  | ORM, fully typed `Mapped[...]` models |
| Alembic       | 1.18.5  | Migrations, applied on container start |
| PostgreSQL    | 18      | Primary datastore |
| Redis         | 8       | Cache, rate-limit storage, sessions |
| Gunicorn      | 26.0.0  | Production WSGI server |
| pydantic      | 2.13.4  | Config validation + request/response schemas |
| Python        | 3.14    | Runtime |

---

## Quick start

```bash
make init          # creates .env from .env.example
$EDITOR .env       # set SECRET_KEY and POSTGRES_PASSWORD
make up            # build + start postgres, redis and the app
make health        # confirm every dependency is reachable
```

The API is on <http://localhost:8000>. `make up` runs the **development**
configuration: hot reload, human-readable logs, database ports published to the
host, and seed data inserted.

Generate a `SECRET_KEY` with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Port conflicts

`POSTGRES_HOST_PORT` and `REDIS_HOST_PORT` control what is published to *your
machine* only. If another stack already owns 5432 or 6379, change them (e.g.
`15432` / `16379`) — the app always reaches the databases at `postgres:5432` and
`redis:6379` over the Compose network, so `POSTGRES_PORT` / `REDIS_PORT` must
stay at the defaults.

### Running the production configuration locally

```bash
make prod    # docker compose -f docker-compose.yml up -d --build
```

This skips `docker-compose.override.yml`: gunicorn instead of the dev server,
JSON logs, no bind mount, no published database ports, non-root user.

---

## Project layout

```
.
├── app/
│   ├── __init__.py          # create_app() factory
│   ├── config.py            # pydantic-settings; env -> validated Settings
│   ├── extensions.py        # db, migrate, cache, limiter, cors, redis_client
│   ├── errors.py            # exception hierarchy + JSON error handlers
│   ├── logging_config.py    # structlog, request-id binding
│   ├── cli.py               # flask seed / wait-for-services / flush-cache
│   ├── models/              # SQLAlchemy models (Base, mixins, User)
│   ├── schemas/             # pydantic request/response models
│   ├── services/            # business logic — the only layer touching the DB
│   ├── api/v1/              # blueprints: health, users
│   └── utils/               # validate_body / validate_query decorators
├── migrations/              # Alembic; versions/ is committed
├── tests/                   # pytest against real Postgres + Redis
├── docker/
│   ├── Dockerfile           # base -> builder -> dev | production
│   ├── entrypoint.sh        # wait for deps -> migrate -> seed -> exec
│   ├── postgres/init/       # first-boot SQL (extensions, timezone)
│   └── redis/redis.conf     # AOF persistence, LRU eviction, memory cap
├── docker-compose.yml       # base stack (production app target)
├── docker-compose.override.yml  # dev: hot reload, published DB ports
├── requirements.txt         # pinned runtime deps
├── requirements-dev.txt     # + pytest, ruff, black, mypy
├── pyproject.toml           # tool config only (ruff/black/mypy/pytest)
├── gunicorn.conf.py
├── wsgi.py
└── Makefile
```

The layering rule: **routes parse and serialise, services own the logic, models
own the schema.** A route should never build a query; a service should never
touch `request`.

---

## API

Base path `/api/v1`.

| Method | Path                | Notes |
| ------ | ------------------- | ----- |
| GET    | `/`                 | Service metadata |
| GET    | `/health/live`      | Liveness — checks *no* dependencies on purpose |
| GET    | `/health/ready`     | Readiness — pings Postgres and Redis; 503 if either is down |
| GET    | `/users`            | Paginated. `?page=&per_page=&active_only=` |
| POST   | `/users`            | Rate limited to 10/min |
| GET    | `/users/<uuid>`     | Read-through Redis cache, 300s TTL |
| PATCH  | `/users/<uuid>`     | Partial update; busts the cache |
| DELETE | `/users/<uuid>`     | 204 |

`/health/live` deliberately checks nothing: if it pinged the database, a brief
Postgres outage would make the orchestrator restart perfectly healthy app
containers and turn a recoverable blip into an outage. Dependency status belongs
in `/health/ready`, which only removes the instance from the load balancer.

### Error format

Every error — validation, HTTP, and unhandled — returns the same envelope:

```json
{"error": {"code": "validation_failed", "message": "...", "details": [...]}}
```

so clients branch on `code` rather than parsing prose. Codes in use:
`validation_failed` (422), `not_found` (404), `conflict` (409), `unauthorized`
(401), `forbidden` (403), `too_many_requests` (429), `service_unavailable` (503),
`internal_error` (500).

Every response also carries `X-Request-ID`, echoed from the request if you send
one, and bound into every log line emitted while handling it.

---

## How Redis is used

Three logical databases keep the workloads from interfering:

| DB | Purpose | Notes |
| -- | ------- | ----- |
| 0  | Flask-Caching | Key prefix `roadtojapan:cache:`, 300s default TTL |
| 1  | Flask-Limiter | Moving-window counters; survives app restarts |
| 2  | `redis_client` | Raw handle for locks, counters, pub/sub |

`redis.conf` sets a 256 MB cap with `allkeys-lru` eviction and AOF persistence
at `everysec` — at most one second of writes lost on a hard crash, without the
throughput cost of fsync-per-write. `FLUSHALL` is disabled.

**Note on the Python client:** `redis` is pinned to 7.4.1, not the newest 8.1.0.
Flask-Limiter's storage layer (`limits`) declares `redis<8.0.0`, so 8.x makes the
dependency graph unresolvable. This caps the *client* only — the Redis server is
8.x. Lift the pin once `limits` widens its bound.

---

## Database workflow

Migrations run automatically on container start (`RUN_MIGRATIONS=1`). To change
the schema:

```bash
# 1. edit or add a model under app/models/, and import it in app/models/__init__.py
# 2. autogenerate a revision
make migrate m="add posts table"
# 3. READ the generated file in migrations/versions/ before trusting it
# 4. apply it
make upgrade
```

Autogenerate does not detect everything (column renames become drop+add, which
loses data; server-side default and constraint changes are often missed). Always
review the revision.

`app/models/base.py` defines an explicit constraint naming convention, so
constraints get stable names like `pk_users` and `fk_posts_user_id_users`
instead of Postgres-assigned ones that Alembic cannot reliably drop later.

Other database commands:

```bash
make psql         # psql session
make downgrade    # roll back one revision
make db-history   # revision log
make seed         # dev admin user: admin@example.com / changeme123
```

---

## Testing

```bash
make test         # against the running stack
make test-local   # one-shot container, no running stack needed
```

Tests run against **real Postgres and Redis** — the whole point is to exercise
the actual stack, so there is no SQLite substitution. The suite creates a
separate `roadtojapan_test` database and uses Redis DB 15, truncating tables and
flushing the cache between tests.

One fixture subtlety worth knowing if you extend `conftest.py`: the `app`
fixture must **not** hold an app context open across tests. Flask reuses an
already-pushed app context for test-client requests instead of pushing its own,
so `teardown_appcontext` never fires, the request's SQLAlchemy session lingers
`idle in transaction`, and its `AccessShareLock` makes the inter-test `TRUNCATE`
block forever.

---

## Code quality

```bash
make lint     # ruff + mypy
make format   # black + ruff --fix
make check    # lint then test
```

Ruff enforces pycodestyle, pyflakes, isort, bugbear, pyupgrade, comprehensions,
blind-except and bandit rules. mypy runs with the pydantic plugin.

---

## Configuration

Every setting is read from the environment (or `.env`) and validated by
pydantic-settings at import, so a missing `SECRET_KEY` or a malformed port fails
loudly at boot instead of surfacing as a `None` on the first request. See
`.env.example` for the full list.

Entrypoint behaviour is env-controlled:

| Variable            | Default | Effect |
| ------------------- | ------- | ------ |
| `WAIT_FOR_SERVICES` | `1`     | Block until Postgres and Redis answer |
| `WAIT_TIMEOUT`      | `60`    | Seconds before giving up |
| `RUN_MIGRATIONS`    | `1`     | `flask db upgrade` on start |
| `RUN_SEED`          | `0`     | `flask seed` on start (`1` in dev) |

---

## Production notes

The `production` image stage ships only the runtime venv plus `app/`,
`migrations/`, `wsgi.py` and `gunicorn.conf.py` — no test code, no build
toolchain, no dev dependencies (373 MB vs 1.02 GB for the dev image). It runs as
UID 1001 under `tini`, with a `HEALTHCHECK` on `/health/live`.

Before deploying beyond local Docker:

- Set `ENV=production` — this turns on `SESSION_COOKIE_SECURE`.
- Replace `CORS_ORIGINS=["*"]` with your actual origins.
- Set a Redis password (`requirepass`) and enable TLS; `protected-mode no` in
  `redis.conf` is safe only because the port is unpublished on a private
  Compose network.
- Move `SECRET_KEY` and `POSTGRES_PASSWORD` out of `.env` into your platform's
  secret store.
- Run migrations as a separate release step rather than on every container
  start, once you have more than one replica.
- Put a reverse proxy in front; `forwarded_allow_ips` is `*` by default and
  should be narrowed to the proxy's address.

---

## Useful commands

```bash
make help          # every target with a description
make logs          # tail all services
make shell         # bash inside the app container
make flask-shell   # REPL with db, models and redis preloaded
make redis-cli     # redis-cli session
make down          # stop, keep data
make destroy       # stop and delete the Postgres/Redis volumes
```
