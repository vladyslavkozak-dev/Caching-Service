import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from payload_cache.api import get_transformer
from payload_cache.main import create_app
from payload_cache.models import Base


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE transformed_strings, payloads"))


@pytest.fixture
def session(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def client(database_url: str, clean_db: None, transformer) -> Iterator[TestClient]:
    app = create_app(database_url)
    app.dependency_overrides[get_transformer] = lambda: transformer
    with TestClient(app) as client:
        yield client
