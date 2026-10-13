from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    # The factory lives on app.state so tests can build an app against their own database.
    with request.app.state.session_factory() as session:
        yield session
