from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from payload_cache.api import router
from payload_cache.config import get_settings
from payload_cache.models import Base


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(database_url or get_settings().database_url, pool_pre_ping=True)
        # Two tables and no schema changes yet, so create_all is enough instead of migrations.
        Base.metadata.create_all(engine)
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
        yield
        engine.dispose()

    app = FastAPI(title="Payload cache", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
