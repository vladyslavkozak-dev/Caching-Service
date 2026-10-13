import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator


def _without_nul(value: str) -> str:
    # JSON allows "\u0000", but Postgres text columns can't store it.
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


# Each string becomes a primary key in the cache table, and a Postgres btree index entry
# can't exceed ~2.7 KB. 500 characters stays under that even for 4-byte UTF-8.
CachedString = Annotated[str, StringConstraints(max_length=500), AfterValidator(_without_nul)]


class PayloadIn(BaseModel):
    list_1: list[CachedString] = Field(min_length=1)
    list_2: list[CachedString] = Field(min_length=1)

    @model_validator(mode="after")
    def check_same_length(self) -> "PayloadIn":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: uuid.UUID
    message: str


class PayloadOut(BaseModel):
    output: str
