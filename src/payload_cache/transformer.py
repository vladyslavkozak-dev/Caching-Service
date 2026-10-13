import time
from collections.abc import Callable

Transformer = Callable[[str], str]


def transform(value: str, delay: float = 0.0) -> str:
    # Stands in for a slow external service, the delay makes cache hits noticeable.
    time.sleep(delay)
    return value.upper()
