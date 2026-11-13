"""Register/update sources from a JSON file: `python -m app.sources.sync sources.json`.

Upserts by name; sources missing from the file are left untouched.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.models import Source, SourceType

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    source_type: SourceType
    feed_url: Annotated[str, StringConstraints(pattern=r"^https?://")] | None = None
    channel_id: Annotated[str, StringConstraints(pattern=r"^UC[A-Za-z0-9_-]{22}$")] | None = None
    enabled: bool = True
    fetch_interval_seconds: int = Field(default=3600, ge=60)

    @model_validator(mode="after")
    def _locator(self) -> Self:
        if self.source_type == SourceType.YOUTUBE and not self.channel_id:
            raise ValueError("youtube sources need channel_id")
        if self.source_type != SourceType.YOUTUBE and not self.feed_url:
            raise ValueError(f"{self.source_type.value} sources need feed_url")
        return self


def load_specs(path: Path) -> list[SourceSpec]:
    return TypeAdapter(list[SourceSpec]).validate_python(json.loads(path.read_text("utf-8")))


async def upsert_sources(sm: async_sessionmaker[AsyncSession], specs: list[SourceSpec]) -> int:
    if not specs:
        return 0
    stmt = pg_insert(Source).values([{"id": uuid.uuid4(), **spec.model_dump()} for spec in specs])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_sources_name",
        set_={
            "source_type": stmt.excluded.source_type,
            "feed_url": stmt.excluded.feed_url,
            "channel_id": stmt.excluded.channel_id,
            "enabled": stmt.excluded.enabled,
            "fetch_interval_seconds": stmt.excluded.fetch_interval_seconds,
            "updated_at": func.now(),
        },
    )
    async with sm.begin() as s:
        await s.execute(stmt)
    return len(specs)


async def main(path: str) -> None:
    specs = load_specs(Path(path))
    engine = make_engine(get_settings().database_url)
    try:
        count = await upsert_sources(make_sessionmaker(engine), specs)
    finally:
        await engine.dispose()
    print(f"synced {count} sources")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.sources.sync <sources.json>")
    asyncio.run(main(sys.argv[1]))
