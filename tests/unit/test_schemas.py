import pytest
from pydantic import ValidationError

from payload_cache.schemas import PayloadIn


def test_accepts_lists_of_same_length():
    payload = PayloadIn(list_1=["a", "b"], list_2=["c", "d"])

    assert payload.list_1 == ["a", "b"]


@pytest.mark.parametrize(
    "data",
    [
        {"list_1": ["a", "b"], "list_2": ["c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": ["a"], "list_2": [1]},
        {"list_1": ["a" * 501], "list_2": ["b"]},
    ],
    ids=["unequal-length", "empty", "missing-list", "non-string", "too-long"],
)
def test_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        PayloadIn.model_validate(data)
