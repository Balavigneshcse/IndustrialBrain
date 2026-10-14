"""JSON schemas for structured outputs (Ollama `format`), validation, and markdown rendering.

The model's JSON is validated with Pydantic; on failure the call is retried once, then the caller
falls back to the extractive answer.
"""
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .client import OllamaClient


class StructuredOutputError(Exception):
    """The model's JSON did not validate twice in a row."""


class WorkOrderDraft(BaseModel):
    insufficientEvidence: bool
    missing: str = Field(description="What the sources lack, when insufficientEvidence is true")
    title: str
    assetTag: str
    problem: str
    priority: Literal["low", "medium", "high", "urgent"]
    priorityReason: str
    tasks: list[str] = Field(max_length=8)
    safety: list[str] = Field(max_length=6)
    parts: list[str] = Field(max_length=8, description="Parts and materials named in the sources")


class ChecklistItem(BaseModel):
    step: str
    source: str = Field(description='Source number, like "S2"')


class ChecklistDraft(BaseModel):
    insufficientEvidence: bool
    missing: str
    title: str
    items: list[ChecklistItem] = Field(max_length=15)


class RcaDraft(BaseModel):
    observedProblem: str
    probableCauses: list[str] = Field(min_length=1, max_length=6)
    recordedActions: list[str] = Field(max_length=6)
    recommendedInvestigation: list[str] = Field(max_length=6)
    preventiveActions: list[str] = Field(max_length=6)


async def generate(llm: OllamaClient, model: type[BaseModel], messages: list[dict], *, max_tokens: int,
                   kind: str) -> tuple[BaseModel, dict]:
    """Returns (validated draft, completion stats). Raises StructuredOutputError or LLMUnavailable."""
    schema = model.model_json_schema()
    problem = ""
    for attempt in (1, 2):
        completion = await llm.complete(messages, max_tokens=max_tokens, schema=schema,
                                        temperature=None if attempt == 1 else 0.0, kind=kind)
        try:
            draft = model.model_validate_json(completion.text)
            return draft, {"prompt_tokens": completion.prompt_tokens, "completion_tokens": completion.completion_tokens,
                           "attempts": attempt}
        except ValidationError as exc:
            problem = f"{exc.error_count()} validation error(s), finish reason {completion.done_reason!r}"
    raise StructuredOutputError(problem)


def render_work_order(draft: WorkOrderDraft) -> str:
    lines = [f"**Work order: {draft.title}**", "",
             f"- **Asset:** {draft.assetTag}",
             f"- **Priority:** {draft.priority.capitalize()}: {draft.priorityReason}",
             f"- **Problem:** {draft.problem}"]
    for heading, items, numbered in (("Tasks", draft.tasks, True), ("Safety", draft.safety, False),
                                     ("Parts and materials", draft.parts, False)):
        if items:
            lines += ["", f"**{heading}**"]
            lines += [f"{i}. {item}" if numbered else f"- {item}" for i, item in enumerate(items, 1)]
    return "\n".join(lines)


def render_checklist(draft: ChecklistDraft) -> str:
    lines = [f"**{draft.title}**", ""]
    for item in draft.items:
        source = item.source.strip().strip("[]").upper()
        valid = source.startswith("S") and source[1:].isdigit() and f"[{source}]" not in item.step
        cite = f" [{source}]" if valid else ""
        lines.append(f"- [ ] {item.step.rstrip()}{cite}")
    return "\n".join(lines)
