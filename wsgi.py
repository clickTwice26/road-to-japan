"""WSGI entrypoint — used by gunicorn and by `flask` CLI auto-discovery."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)  # noqa: S104 - dev convenience only
