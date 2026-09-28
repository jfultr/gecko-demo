"""FastAPI application entry point."""

from fastapi import FastAPI

from .config import Settings
from .db import Database
from .errors import install_error_handlers
from .routes import jobs, media, upload


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.prepare()
    database = Database(settings.database_path)
    database.initialize()
    app = FastAPI(title="Gecko Demo API", version="1.0")
    app.state.settings = settings
    app.state.database = database
    install_error_handlers(app)
    app.include_router(upload.router)
    app.include_router(jobs.router)
    app.include_router(media.router)
    return app


app = create_app()
