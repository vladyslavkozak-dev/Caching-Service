import uuid

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


def test_create_and_read_sample(client):
    created = client.post("/payload", json=SAMPLE)

    assert created.status_code == 201
    assert created.json()["message"] == "Payload created"

    payload = client.get(f"/payload/{created.json()['id']}")

    assert payload.status_code == 200
    assert payload.json() == {
        "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, "
        "LAST STRING"
    }


def test_repeated_create_returns_existing_id(client, transformer):
    first = client.post("/payload", json=SAMPLE)
    transformer.calls.clear()

    second = client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "message": "Payload already exists"}
    assert transformer.calls == []


def test_overlapping_payload_transforms_only_new_strings(client, transformer):
    client.post("/payload", json=SAMPLE)
    transformer.calls.clear()

    response = client.post(
        "/payload",
        json={"list_1": ["first string", "new string"], "list_2": ["last string", "other string"]},
    )

    assert response.status_code == 201
    assert transformer.calls == ["new string"]


def test_invalid_payload_is_rejected_before_transforming(client, transformer):
    response = client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c"]})

    assert response.status_code == 422
    assert transformer.calls == []


def test_nul_character_is_rejected(client):
    response = client.post(
        "/payload",
        content=r'{"list_1": ["a\u0000b"], "list_2": ["c"]}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


def test_read_unknown_payload(client):
    assert client.get(f"/payload/{uuid.uuid4()}").status_code == 404


def test_read_with_malformed_id(client):
    assert client.get("/payload/not-a-uuid").status_code == 422
