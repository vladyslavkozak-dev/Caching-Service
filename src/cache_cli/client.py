import uuid
from dataclasses import dataclass

import httpx

from payload_cache.schemas import PayloadCreated, PayloadIn, PayloadOut


@dataclass(frozen=True)
class CreatedPayload:
    id: uuid.UUID
    created: bool


class CacheClient:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(self, payload: PayloadIn) -> CreatedPayload:
        response = self._http.post("/payload", json=payload.model_dump())
        response.raise_for_status()
        body = PayloadCreated.model_validate(response.json())
        return CreatedPayload(id=body.id, created=response.status_code == httpx.codes.CREATED)

    def read(self, payload_id: uuid.UUID) -> str:
        response = self._http.get(f"/payload/{payload_id}")
        response.raise_for_status()
        return PayloadOut.model_validate(response.json()).output
