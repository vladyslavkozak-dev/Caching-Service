import json
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

import httpx
from pydantic import ValidationError

from cache_cli.client import CacheClient
from cache_cli.settings import STDIO, CliSettings, parse_args
from payload_cache.schemas import PayloadIn

# Generous because every uncached string costs a call to the slow transformer.
REQUEST_TIMEOUT = 60.0


def load_payload(settings: CliSettings, stdin: TextIO) -> PayloadIn:
    if settings.json_input is not None:
        raw = settings.json_input
    elif settings.input == STDIO:
        raw = stdin.read()
    else:
        raw = Path(settings.input).read_text(encoding="utf-8")
    return PayloadIn.model_validate_json(raw)


@contextmanager
def open_output(path: str, stdout: TextIO) -> Iterator[TextIO]:
    if path == STDIO:
        yield stdout
        return
    with open(path, "w", encoding="utf-8") as file:
        yield file


def run(settings: CliSettings, client: CacheClient, stdin: TextIO, stdout: TextIO) -> None:
    payload = load_payload(settings, stdin)
    with open_output(settings.output, stdout) as out:
        for iteration in range(1, settings.repeat + 1):
            started = time.perf_counter()
            created = client.create(payload)
            output = client.read(created.id)
            record = {
                "iteration": iteration,
                "id": str(created.id),
                "created": created.created,
                "output": output,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(args: list[str] | None = None) -> None:
    try:
        settings = parse_args(args)
        with httpx.Client(base_url=str(settings.host), timeout=REQUEST_TIMEOUT) as http:
            run(settings, CacheClient(http), sys.stdin, sys.stdout)
    except ValidationError as exc:
        print(f"cache-cli: invalid input\n{_format_errors(exc)}", file=sys.stderr)
        raise SystemExit(2) from None
    except httpx.HTTPStatusError as exc:
        response = exc.response
        sys.exit(f"cache-cli: server returned {response.status_code}: {response.text}")
    except (httpx.HTTPError, OSError) as exc:
        sys.exit(f"cache-cli: {exc}")


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        lines.append(f"  {location}: {error['msg']}" if location else f"  {error['msg']}")
    return "\n".join(lines)
