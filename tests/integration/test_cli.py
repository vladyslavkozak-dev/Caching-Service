import io
import json

from cache_cli.client import CacheClient
from cache_cli.main import run
from cache_cli.settings import parse_args

SAMPLE = json.dumps(
    {
        "list_1": ["first string", "second string", "third string"],
        "list_2": ["other string", "another string", "last string"],
    }
)


def test_repeated_runs_hit_the_cache(client, transformer):
    stdout = io.StringIO()

    run(parse_args(["-j", SAMPLE, "-r", "3"]), CacheClient(client), io.StringIO(), stdout)

    records = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [r["created"] for r in records] == [True, False, False]
    assert len({r["id"] for r in records}) == 1
    assert records[0]["output"] == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )
    assert len(transformer.calls) == 6
