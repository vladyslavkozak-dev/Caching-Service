import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from payload_cache.models import Payload, TransformedString
from payload_cache.transformer import Transformer


@dataclass(frozen=True)
class CreateResult:
    id: uuid.UUID
    created: bool


def payload_hash(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    # JSON keeps list boundaries, so (["a", "b"], ["c"]) and (["a"], ["b", "c"]) differ.
    canonical = json.dumps([list_1, list_2], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


def get_transformed(
    session: Session, values: Iterable[str], transform: Transformer
) -> dict[str, str]:
    """Map each value to its transformation, calling `transform` only for uncached values.

    Ends the current transaction before calling `transform`.
    """
    unique = set(values)
    rows = session.execute(
        select(TransformedString.source, TransformedString.result).where(
            TransformedString.source.in_(unique)
        )
    )
    cached = dict(rows.tuples().all())

    missing = unique - cached.keys()
    if not missing:
        return cached

    # Return the connection to the pool while waiting on the slow transformer, otherwise
    # a burst of uncached requests exhausts the pool.
    session.commit()
    fresh = {value: transform(value) for value in missing}

    # Rows go in sorted order so concurrent inserts lock them in the same order and can't
    # deadlock. A concurrent request may cache the same strings first, its results are identical.
    session.execute(
        insert(TransformedString)
        .values([{"source": source, "result": result} for source, result in sorted(fresh.items())])
        .on_conflict_do_nothing()
    )
    return cached | fresh


def create_payload(
    session: Session, list_1: Sequence[str], list_2: Sequence[str], transform: Transformer
) -> CreateResult:
    input_hash = payload_hash(list_1, list_2)
    existing_id = _find_payload_id(session, input_hash)
    if existing_id is not None:
        return CreateResult(existing_id, created=False)

    transformed = get_transformed(session, [*list_1, *list_2], transform)
    output = ", ".join(transformed[value] for value in interleave(list_1, list_2))

    payload_id = session.scalar(
        insert(Payload)
        .values(input_hash=input_hash, output=output)
        .on_conflict_do_nothing(index_elements=[Payload.input_hash])
        .returning(Payload.id)
    )
    session.commit()

    if payload_id is None:
        # An identical request committed between our lookup and insert, reuse its id.
        return CreateResult(_find_payload_id(session, input_hash), created=False)
    return CreateResult(payload_id, created=True)


def get_payload_output(session: Session, payload_id: uuid.UUID) -> str | None:
    payload = session.get(Payload, payload_id)
    return payload.output if payload else None


def _find_payload_id(session: Session, input_hash: str) -> uuid.UUID | None:
    return session.scalar(select(Payload.id).where(Payload.input_hash == input_hash))
