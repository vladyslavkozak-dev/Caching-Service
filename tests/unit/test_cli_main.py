import io
import json
import uuid

import httpx
import pytest

from cache_cli.client import CacheClient
from cache_cli.main import main, run
from cache_cli.settings import parse_args

PAYLOAD = '{"list_1": ["a"], "list_2": ["b"]}'
PAYLOAD_ID = uuid.uuid4()


class FakeService:
    """Answers like the real service: 201 for the first create, 200 afterwards."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            first = sum(r.method == "POST" for r in self.requests) == 1
            return httpx.Response(
                201 if first else 200, json={"id": str(PAYLOAD_ID), "message": "ok"}
            )
        return httpx.Response(200, json={"output": "A, B"})


@pytest.fixture
def service() -> FakeService:
    return FakeService()


@pytest.fixture
def client(service) -> CacheClient:
    return CacheClient(httpx.Client(base_url="http://test", transport=httpx.MockTransport(service)))


def records(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines()]


def test_writes_one_record_per_iteration(client, service):
    stdout = io.StringIO()

    run(parse_args(["-j", PAYLOAD, "-r", "3"]), client, io.StringIO(), stdout)

    result = records(stdout.getvalue())
    assert [r["iteration"] for r in result] == [1, 2, 3]
    assert [r["created"] for r in result] == [True, False, False]
    assert {r["id"] for r in result} == {str(PAYLOAD_ID)}
    assert {r["output"] for r in result} == {"A, B"}
    assert json.loads(service.requests[0].content) == json.loads(PAYLOAD)


def test_reads_stdin_and_writes_file(client, tmp_path):
    output_file = tmp_path / "out.jsonl"

    run(
        parse_args(["-i", "-", "-o", str(output_file)]), client, io.StringIO(PAYLOAD), io.StringIO()
    )

    assert records(output_file.read_text())[0]["output"] == "A, B"


def test_invalid_payload_is_rejected_before_any_request(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["-j", '{"list_1": ["a", "b"], "list_2": ["c"]}', "-h", "http://127.0.0.1:9"])

    assert exit_info.value.code == 2
    assert "same length" in capsys.readouterr().err


def test_unreachable_server_exits_with_error():
    with pytest.raises(SystemExit) as exit_info:
        main(["-j", PAYLOAD, "-h", "http://127.0.0.1:9"])

    assert "cache-cli:" in str(exit_info.value.code)
