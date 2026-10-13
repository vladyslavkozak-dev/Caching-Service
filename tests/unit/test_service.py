import pytest

from payload_cache.service import interleave, payload_hash


def test_interleave_alternates_lists():
    assert interleave(["a", "b", "c"], ["x", "y", "z"]) == ["a", "x", "b", "y", "c", "z"]


def test_interleave_rejects_unequal_lengths():
    with pytest.raises(ValueError):
        interleave(["a", "b"], ["x"])


def test_payload_hash_is_stable():
    assert payload_hash(["a", "b"], ["c", "d"]) == payload_hash(["a", "b"], ["c", "d"])


def test_payload_hash_depends_on_order():
    assert payload_hash(["a", "b"], ["c", "d"]) != payload_hash(["b", "a"], ["c", "d"])
    assert payload_hash(["a", "b"], ["c", "d"]) != payload_hash(["c", "d"], ["a", "b"])


def test_payload_hash_keeps_list_boundaries():
    assert payload_hash(["a", "b"], ["c"]) != payload_hash(["a"], ["b", "c"])
