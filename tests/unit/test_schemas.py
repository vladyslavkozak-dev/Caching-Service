import pytest
from pydantic import ValidationError

from payload_cache.schemas import PayloadIn


def test_accepts_lists_of_same_length():
    payload = PayloadIn(list_1=["a", "b"], list_2=["c", "d"])

    assert payload.list_1 == ["a", "b"]


def test_accepts_non_ascii_strings():
    payload = PayloadIn(list_1=["Grüße", "日本"], list_2=["😀", "ß"])

    assert payload.list_2 == ["😀", "ß"]


@pytest.mark.parametrize(
    "data",
    [
        {"list_1": ["a", "b"], "list_2": ["c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": ["a"], "list_2": [1]},
        {"list_1": ["a" * 501], "list_2": ["b"]},
        {"list_1": ["a\x00b"], "list_2": ["c"]},
    ],
    ids=[
        "unequal-length",
        "empty",
        "missing-list",
        "non-string",
        "too-long",
        "nul-character",
    ],
)
def test_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        PayloadIn.model_validate(data)
