"""Deterministic mock executor: planning -> researching -> verifying -> reporting."""

import asyncio
import re
from typing import Any

from app.research.base import ResearchResult, SaveCheckpoint, Source

STAGES: tuple[str, ...] = ("planning", "researching", "verifying", "reporting")


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "topic"


class MockResearchExecutor:
    def __init__(self, stage_delay_seconds: float = 0.0) -> None:
        self.stage_delay_seconds = stage_delay_seconds

    async def run(
        self,
        topic: str,
        checkpoint: dict[str, Any] | None,
        save_checkpoint: SaveCheckpoint,
    ) -> ResearchResult:
        state: dict[str, Any] = dict((checkpoint or {}).get("data") or {})
        done_stage = (checkpoint or {}).get("stage")
        start = STAGES.index(done_stage) + 1 if done_stage in STAGES else 0
        slug = _slug(topic)

        for stage in STAGES[start:]:
            await asyncio.sleep(self.stage_delay_seconds)
            if stage == "planning":
                state["questions"] = [
                    f"What is {topic}?",
                    f"What are the key developments in {topic}?",
                    f"What are the open problems in {topic}?",
                ]
            elif stage == "researching":
                state["sources"] = [
                    {"url": f"https://example.com/{slug}/{i}", "title": f"{topic} - source {i}"}
                    for i in range(1, 4)
                ]
            elif stage == "verifying":
                state["verified_sources"] = len(state["sources"])
            elif stage == "reporting":
                lines = [f"# Research report: {topic}", ""]
                lines += [f"- {q}" for q in state["questions"]]
                lines += ["", f"Verified sources: {state['verified_sources']}"]
                state["report"] = "\n".join(lines)
            await save_checkpoint(stage, state)

        return ResearchResult(
            content=state["report"],
            sources=[Source(url=s["url"], title=s["title"]) for s in state["sources"]],
        )
