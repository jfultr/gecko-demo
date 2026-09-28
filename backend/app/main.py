"""FastAPI application entry point."""

from fastapi import FastAPI

from .config import Settings
from .db import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.prepare()
    database = Database(settings.database_path)
    database.initialize()
    app = FastAPI(title="Gecko Demo API", version="1.0")
    app.state.settings = settings
    app.state.database = database
    return app


app = create_app()
