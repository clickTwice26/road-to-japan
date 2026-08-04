#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint: block on dependencies, optionally migrate, then exec
# the command. `exec` matters — it keeps the app as PID 1's direct child so
# SIGTERM reaches gunicorn and shutdown stays graceful.
# ---------------------------------------------------------------------------
set -Eeuo pipefail

export FLASK_APP="${FLASK_APP:-wsgi:app}"

log() { printf '[entrypoint] %s\n' "$*" >&2; }

if [[ "${WAIT_FOR_SERVICES:-1}" == "1" ]]; then
    log "waiting for postgres and redis..."
    flask wait-for-services --timeout "${WAIT_TIMEOUT:-60}"
fi

if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
    log "applying database migrations..."
    flask db upgrade
    log "migrations up to date"
fi

if [[ "${RUN_SEED:-0}" == "1" ]]; then
    log "seeding database..."
    flask seed
fi

log "starting: $*"
exec "$@"
