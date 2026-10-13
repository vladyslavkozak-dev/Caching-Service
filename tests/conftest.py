import pytest


class CountingTransformer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, value: str) -> str:
        self.calls.append(value)
        return value.upper()


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()
