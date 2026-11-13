"""Research execution interface. The worker only depends on this module."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

# Called by an executor after finishing a stage. Persists {"stage": ..., "data": ...}.
# Raises app.jobs.repository.LeaseLost if this worker no longer owns the job.
SaveCheckpoint = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class Source:
    url: str
    title: str | None = None


@dataclass(frozen=True)
class ResearchResult:
    content: str
    sources: list[Source] = field(default_factory=list)


class ResearchExecutor(Protocol):
    async def run(
        self,
        topic: str,
        checkpoint: dict[str, Any] | None,
        save_checkpoint: SaveCheckpoint,
    ) -> ResearchResult:
        """Run (or resume from `checkpoint`) research for `topic`."""
        ...
