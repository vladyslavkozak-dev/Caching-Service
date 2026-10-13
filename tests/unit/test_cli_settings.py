import pytest
from pydantic import ValidationError

from cache_cli.settings import STDIO, parse_args

PAYLOAD = '{"list_1": ["a"], "list_2": ["b"]}'


def test_defaults():
    settings = parse_args(["--json", PAYLOAD])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.output == STDIO


def test_short_and_long_options_are_equivalent():
    long = parse_args(
        ["--host", "http://api:9000", "--repeat", "3", "--json", PAYLOAD, "--output", "out.jsonl"]
    )
    short = parse_args(["-h", "http://api:9000", "-r", "3", "-j", PAYLOAD, "-o", "out.jsonl"])

    assert short == long
    assert str(short.host) == "http://api:9000/"
    assert short.repeat == 3
    assert short.output == "out.jsonl"


def test_input_accepts_existing_file_and_stdin(tmp_path):
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(PAYLOAD)

    assert parse_args(["-i", str(payload_file)]).input == str(payload_file)
    assert parse_args(["-i", STDIO]).input == STDIO


def test_environment_is_ignored(monkeypatch):
    monkeypatch.setenv("HOST", "http://elsewhere:1")
    monkeypatch.setenv("REPEAT", "5")

    settings = parse_args(["-j", PAYLOAD])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-i", STDIO, "-j", PAYLOAD],
        ["-i", "missing.json"],
        ["-j", PAYLOAD, "-r", "0"],
        ["-j", PAYLOAD, "-h", "ftp://example.com"],
    ],
    ids=["no-source", "both-sources", "missing-file", "zero-repeat", "non-http-host"],
)
def test_rejects_invalid_arguments(args):
    with pytest.raises(ValidationError):
        parse_args(args)


def test_help_is_long_option_only(capsys):
    with pytest.raises(SystemExit) as exit_info:
        parse_args(["--help"])

    assert exit_info.value.code == 0
    assert "--host" in capsys.readouterr().out
