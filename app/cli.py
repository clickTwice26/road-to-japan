"""Custom ``flask`` CLI commands."""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import text

from app.extensions import db, redis_client


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed)
    app.cli.add_command(wait_for_services)
    app.cli.add_command(flush_cache)

    @app.shell_context_processor
    def _shell_context() -> dict[str, object]:
        from app import models

        return {"db": db, "redis": redis_client, "models": models, "User": models.User}


@click.command("seed")
@with_appcontext
def seed() -> None:
    """Insert a development admin user (idempotent)."""
    from sqlalchemy import select

    from app.models import User

    email = "admin@example.com"
    if db.session.scalar(select(User.id).where(User.email == email)):
        click.echo(f"{email} already exists — nothing to do.")
        return

    user = User(email=email, full_name="Admin User")
    user.set_password("changeme123")
    db.session.add(user)
    db.session.commit()
    click.secho(f"Created {email} (password: changeme123)", fg="green")


@click.command("wait-for-services")
@click.option("--timeout", default=60, show_default=True, help="Seconds to keep retrying.")
@with_appcontext
def wait_for_services(timeout: int) -> None:
    """Block until Postgres and Redis both answer, or fail after ``--timeout``."""
    import time

    deadline = time.monotonic() + timeout
    for name, probe in (
        ("postgres", lambda: db.session.execute(text("SELECT 1"))),
        ("redis", redis_client.ping),
    ):
        while True:
            try:
                probe()
                click.secho(f"{name} is ready", fg="green")
                break
            except Exception as exc:  # any failure means "not ready yet" — retry
                if time.monotonic() > deadline:
                    raise SystemExit(f"{name} not ready after {timeout}s: {exc}") from exc
                click.echo(f"waiting for {name}...")
                time.sleep(1)


@click.command("flush-cache")
@with_appcontext
def flush_cache() -> None:
    """Drop every key in the application cache database."""
    from app.extensions import cache

    cache.clear()
    click.secho("Cache cleared.", fg="green")
