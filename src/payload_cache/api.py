import uuid
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from payload_cache import service
from payload_cache.config import Settings, get_settings
from payload_cache.db import get_session
from payload_cache.schemas import PayloadCreated, PayloadIn, PayloadOut
from payload_cache.transformer import Transformer, transform

router = APIRouter(prefix="/payload", tags=["payload"])


def get_transformer(settings: Annotated[Settings, Depends(get_settings)]) -> Transformer:
    return partial(transform, delay=settings.transform_delay)


SessionDep = Annotated[Session, Depends(get_session)]
TransformerDep = Annotated[Transformer, Depends(get_transformer)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": PayloadCreated, "description": "Payload exists"}},
)
def create_payload(
    body: PayloadIn, response: Response, session: SessionDep, transformer: TransformerDep
) -> PayloadCreated:
    result = service.create_payload(session, body.list_1, body.list_2, transformer)
    if not result.created:
        response.status_code = status.HTTP_200_OK
        return PayloadCreated(id=result.id, message="Payload already exists")
    return PayloadCreated(id=result.id, message="Payload created")


@router.get("/{payload_id}")
def read_payload(payload_id: uuid.UUID, session: SessionDep) -> PayloadOut:
    output = service.get_payload_output(session, payload_id)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadOut(output=output)
