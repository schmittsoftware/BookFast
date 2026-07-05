import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import seed
from app.config import Settings
from app.container import build_deps
from app.db import Base, make_engine, make_session_factory
from app.web.routes import router
from app.web.routes_workflows import router as workflows_router

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    Path("./var").mkdir(exist_ok=True)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    deps = build_deps(settings)

    with session_factory() as db:
        seed.seed_if_empty(db, deps)

    app = FastAPI(title=settings.app_name)
    app.state.deps = deps
    app.state.session_factory = session_factory
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(router)
    app.include_router(workflows_router)
    return app


app = create_app()
