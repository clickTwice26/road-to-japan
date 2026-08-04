# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Multi-stage build. `dev` keeps the test/lint toolchain; `production` ships
# only the runtime venv on a slim base, running as an unprivileged user.
# ---------------------------------------------------------------------------

ARG PYTHON_VERSION=3.14

# --- base ------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- builder ---------------------------------------------------------------
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt requirements-dev.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# --- dev -------------------------------------------------------------------
FROM builder AS dev

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-dev.txt

ENV FLASK_APP=wsgi:app \
    FLASK_DEBUG=1

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY . .

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["flask", "run", "--host=0.0.0.0", "--port=8000", "--reload"]

# --- production ------------------------------------------------------------
FROM base AS production

# Non-root: the app never needs to write anywhere outside /tmp.
RUN groupadd --gid 1001 app \
    && useradd --uid 1001 --gid app --create-home --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /opt/venv /opt/venv

COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app wsgi.py gunicorn.conf.py ./

ENV FLASK_APP=wsgi:app \
    ENV=production \
    PORT=8000

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/v1/health/live" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
