import uuid

from payload_cache.service import create_payload, get_payload_output


def test_sample_from_spec(session, transformer):
    result = create_payload(
        session,
        ["first string", "second string", "third string"],
        ["other string", "another string", "last string"],
        transformer,
    )

    assert result.created
    assert get_payload_output(session, result.id) == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_same_input_reuses_payload(session, transformer):
    first = create_payload(session, ["a", "b"], ["c", "d"], transformer)
    calls_after_first = len(transformer.calls)

    second = create_payload(session, ["a", "b"], ["c", "d"], transformer)

    assert not second.created
    assert second.id == first.id
    assert len(transformer.calls) == calls_after_first


def test_cached_strings_are_not_transformed_again(session, transformer):
    create_payload(session, ["a", "b"], ["c", "d"], transformer)
    transformer.calls.clear()

    result = create_payload(session, ["a", "e"], ["c", "f"], transformer)

    assert result.created
    assert sorted(transformer.calls) == ["e", "f"]
    assert get_payload_output(session, result.id) == "A, C, E, F"


def test_duplicates_in_request_are_transformed_once(session, transformer):
    create_payload(session, ["a", "a"], ["a", "b"], transformer)

    assert sorted(transformer.calls) == ["a", "b"]


def test_unknown_payload_returns_none(session):
    assert get_payload_output(session, uuid.uuid4()) is None
