"""Question answering: follow-up rewriting, retrieval, generation, grounding checks, evidence strength
and the query log.

`answer_events` is the one implementation behind POST /chat/query (which returns the final event as
JSON) and POST /chat/stream (which forwards every event as Server-Sent Events):

    status   {"stage": "rewriting" | "retrieving" | "generating" | "queued", "position"?: n}
    sources  {"question": standalone question, "citations": [...]}   the evidence given to the model
    token    {"text": "..."}                                            free-text answers, as generated
    done     ChatAnswer                                                 the final, checked answer
"""
import asyncio
import re
import time
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass, field

import anyio
import structlog
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db.models import QueryLog
from ..llm import checks, prompts
from ..llm.client import LLMBusy, LLMUnavailable, OllamaClient, get_llm
from ..llm.structured import ChecklistDraft, WorkOrderDraft, render_checklist, render_work_order
from ..schemas.chat import ChatAnswer, ChatQueryRequest, Citation, ConversationTurn
from . import store
from .answers import INSUFFICIENT_EVIDENCE, classify_query, generate_answer
from .entities import extract_entities

log = structlog.get_logger("qa")

LLM_OFFLINE = "LLM offline: showing top evidence."
INTERRUPTED = "Generation was interrupted: the language model stopped responding."
FOLLOW_UP = re.compile(r"\b(it|its|this|that|these|those|they|them|their|there|same|above|previous|earlier|"
                       r"former|latter|more|else|also|again)\b|^\s*(and|but|so|what about|how about)\b", re.IGNORECASE)
HISTORY_TURNS = 6                # the last 3 exchanges
STRUCTURED = {"work_order": WorkOrderDraft, "checklist": ChecklistDraft}
STRUCTURED_TOKENS = 700
BUSY_DETAIL = "The language model is busy with other questions. Try again in a minute."


@dataclass
class Outcome:
    answer: str
    mode: str
    evidence: list[dict] = field(default_factory=list)
    refused: bool = False
    notice: str | None = None
    warnings: list[str] = field(default_factory=list)
    grounding: checks.Grounding | None = None
    strength: str | None = None
    structured: dict | None = None
    model: str | None = None
    prompt_version: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _status(stage: str, **extra) -> dict:
    return {"event": "status", "data": {"stage": stage, **extra}}


def prior_turns(history: list[ConversationTurn] | None, question: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for turn in history or []:
        role = "user" if (turn.role or "").lower() == "user" else "assistant"
        text = " ".join((turn.content or "").split())
        if text:
            turns.append((role, (checks.CITATION.sub("", text) if role == "assistant" else text)[:400]))
    if turns and turns[-1] == ("user", " ".join(question.split())[:400]):
        turns.pop()  # the current UI sends the question itself as the last turn
    return turns[-HISTORY_TURNS:]


def needs_rewrite(question: str, turns: list[tuple[str, str]]) -> bool:
    if not any(role == "user" for role, _ in turns):
        return False
    if FOLLOW_UP.search(question):
        return True
    return len(question.split()) <= 5 and not extract_entities(question)["asset_tags"]


async def standalone_question(llm: OllamaClient, question: str, turns: list[tuple[str, str]]) -> str:
    """The follow-up rewritten to stand alone (a short model call); without the model, the previous
    question is prepended so retrieval still sees the subject."""
    if llm.available():
        try:
            completion = await llm.complete(prompts.rewrite_messages(turns, question), max_tokens=80,
                                            temperature=0.0, kind="rewrite")
            lines = [line.strip() for line in completion.text.strip().splitlines() if line.strip()]
            text = re.sub(r"^standalone question:\s*", "", lines[0], flags=re.IGNORECASE).strip("\"' ") if lines else ""
            if 3 <= len(text) <= 400:
                return text
        except (LLMUnavailable, LLMBusy) as exc:
            log.warning("rewrite_failed", error=str(exc))
    last_question = next((text for role, text in reversed(turns) if role == "user"), "")
    return f"{last_question} {question}".strip()


async def _unknown_assets(session: AsyncSession, question: str, asset_tag: str) -> Outcome | None:
    """Asset tags named in the question (or the tag filter) that no indexed document mentions get an
    explicit "no evidence" reply instead of an answer built from another asset's records."""
    requested = set(extract_entities(question)["asset_tags"])
    if asset_tag:
        requested.add(asset_tag)
    if not requested:
        return None
    unknown = sorted(requested - await store.known_asset_tags(session))
    if unknown and len(unknown) == len(requested):
        return Outcome(answer=f"No indexed documents mention {', '.join(unknown)}, so I can't answer about "
                              f"{'it' if len(unknown) == 1 else 'them'}. Upload records for that equipment first.",
                       mode="no-evidence", refused=True, strength="low")
    return None


async def _extractive(question: str, evidence: list[dict], desired_format: str, notice: str | None) -> Outcome:
    text, _, _ = await run_in_threadpool(generate_answer, question, evidence, desired_format)
    return Outcome(answer=text, mode="extractive", evidence=evidence, notice=notice,
                   strength=checks.evidence_strength([e["score"] for e in evidence], None, False))


def citations(evidence: list[dict], cited: list[int] | None = None) -> list[Citation]:
    cited_set = set(cited or [])
    return [
        Citation(label=f"S{number}", cited=number in cited_set,
                 docId=str(item["metadata"]["document_id"]), filename=item["metadata"]["source"],
                 source=item["metadata"]["source"], page=item["metadata"]["page"],
                 documentType=item["metadata"]["document_type"], excerpt=item["text"][:360],
                 textSnippet=item["text"][:360], relevance=round(item["score"], 2))
        for number, item in enumerate(evidence, 1)
    ]


async def _generate(llm: OllamaClient, messages: list[dict], sink: list[str], stats: dict, *, max_tokens: int,
                    schema: dict | None = None, temperature: float | None = None, kind: str,
                    emit_tokens: bool) -> AsyncIterator[dict]:
    async with aclosing(llm.stream(messages, max_tokens=max_tokens, schema=schema, temperature=temperature,
                                   kind=kind)) as events:
        async for event in events:
            if event["type"] == "queued":
                yield _status("queued", position=event["position"])
            elif event["type"] == "token":
                sink.append(event["text"])
                if emit_tokens:
                    yield {"event": "token", "data": {"text": event["text"]}}
            elif event["type"] == "done":
                stats.update(event)


def _finish_text(answer: str, evidence: list[dict], advice: frozenset[str] = frozenset()) -> Outcome:
    """Normalizes citations, runs the grounding checks and labels evidence strength."""
    answer, invalid = checks.normalize_citations(answer.strip(), len(evidence))
    refused = checks.is_refusal(answer)
    if not refused:  # an answer followed by "Insufficient evidence: <the uncovered part>" is not a refusal
        answer = checks.TRAILING_REFUSAL.sub(lambda m: m.group(1) + "Not covered by the sources:", answer)
    grounding = None
    if not refused:
        grounding = checks.check(answer, [item["text"] for item in evidence], advice)
        grounding.invalidCitations = invalid
    return Outcome(answer=answer, mode="llm", evidence=evidence, refused=refused, grounding=grounding,
                   warnings=grounding.warnings() if grounding else [],
                   strength=checks.evidence_strength([item["score"] for item in evidence], grounding, refused))


def _finish_structured(desired_format: str, draft: BaseModel, evidence: list[dict]) -> Outcome:
    if draft.insufficientEvidence:
        missing = draft.missing.strip().rstrip(".") or "the sources do not describe what is needed"
        outcome = _finish_text(f"Insufficient evidence: {missing}.", evidence)
    elif isinstance(draft, WorkOrderDraft):
        # Problem and priority reason are facts and need citations; tasks, safety steps and parts are advice.
        advice = [item.strip() for item in (*draft.tasks, *draft.safety, *draft.parts)]
        outcome = _finish_text("\n".join([draft.problem, draft.priorityReason, *advice]), evidence,
                               frozenset(checks.normalize_citations(item, len(evidence))[0] for item in advice))
        outcome.answer = checks.normalize_citations(render_work_order(draft), len(evidence))[0]
    else:
        rendered = render_checklist(draft)
        outcome = _finish_text(rendered.split("\n", 2)[-1], evidence)  # the items, without the title
        outcome.answer = checks.normalize_citations(rendered, len(evidence))[0]
    outcome.structured = draft.model_dump()
    return outcome


async def answer_events(session: AsyncSession, user_id: int, body: ChatQueryRequest) -> AsyncIterator[dict]:
    settings = get_settings()
    llm = get_llm()
    started = time.perf_counter()
    question = body.question.strip()
    asset_tag = (body.assetTag or "").strip().upper()
    desired_format = (body.desiredFormat or "quick_answer").strip().lower()
    turns = prior_turns(body.history, question)
    standalone = question
    sink: list[str] = []
    stats: dict = {}
    outcome: Outcome | None = None
    prompt_id: str | None = None
    try:
        if classify_query(question) == "greeting":
            text, _, _ = generate_answer(question, [])
            outcome = Outcome(answer=text, mode="assistant")
        else:
            if needs_rewrite(question, turns):
                yield _status("rewriting")
                standalone = await standalone_question(llm, question, turns)
            outcome = await _unknown_assets(session, standalone, asset_tag)
        if outcome is None:
            yield _status("retrieving")
            evidence = await store.search(session, standalone, asset_tag, limit=settings.llm_context_chunks)
            if not evidence or evidence[0]["score"] < settings.min_evidence_score:
                # The reranker found nothing relevant enough: say so instead of answering from weak matches.
                outcome = Outcome(answer=INSUFFICIENT_EVIDENCE, mode="no-evidence", refused=True, strength="low")
            elif not llm.available():
                outcome = await _extractive(standalone, evidence, desired_format, LLM_OFFLINE if llm.enabled else None)
        if outcome is None:
            draft_model = STRUCTURED.get(desired_format)
            max_tokens = STRUCTURED_TOKENS if draft_model else settings.llm_max_answer_tokens
            prompt = prompts.load(desired_format if draft_model else "answer")
            prompt_id = prompt.id
            source_text, used = prompts.source_blocks(evidence, prompts.source_budget_chars(max_tokens))
            evidence = evidence[:used]
            yield {"event": "sources", "data": {"question": standalone,
                                                "citations": [c.model_dump() for c in citations(evidence)]}}
            messages = prompts.grounded_messages(prompt, source_text, standalone, desired_format)
            yield _status("generating")
            try:
                if draft_model is None:
                    async with aclosing(_generate(llm, messages, sink, stats, max_tokens=max_tokens, kind="answer",
                                                  emit_tokens=True)) as events:
                        async for event in events:
                            yield event
                    if not "".join(sink).strip():
                        raise LLMUnavailable("empty answer")
                    outcome = _finish_text("".join(sink), evidence)
                    if stats.get("done_reason") == "length":
                        outcome.warnings.append("The answer reached the length limit and may be cut off.")
                else:
                    draft = None
                    for temperature in (None, 0.0):  # validate; retry once, more deterministically
                        sink.clear()
                        async with aclosing(_generate(llm, messages, sink, stats, max_tokens=max_tokens,
                                                      schema=draft_model.model_json_schema(), temperature=temperature,
                                                      kind=desired_format, emit_tokens=False)) as events:
                            async for event in events:
                                yield event
                        try:
                            draft = draft_model.model_validate_json("".join(sink))
                            break
                        except ValidationError as exc:
                            log.warning("structured_output_invalid", format=desired_format, errors=exc.error_count())
                    if draft is None:
                        outcome = await _extractive(standalone, evidence, desired_format,
                                                    "The model's structured output did not validate; showing top evidence.")
                    else:
                        outcome = _finish_structured(desired_format, draft, evidence)
            except LLMUnavailable as exc:
                log.warning("llm_unavailable", error=str(exc))
                if sink and draft_model is None:
                    outcome = _finish_text("".join(sink), evidence)
                    outcome.warnings.append(INTERRUPTED)
                else:
                    outcome = await _extractive(standalone, evidence, desired_format, LLM_OFFLINE)
            except LLMBusy:
                raise HTTPException(429, BUSY_DETAIL, headers={"Retry-After": "30"}) from None
            if outcome.mode == "llm":
                outcome.model, outcome.prompt_version = llm.model, prompt_id
                outcome.prompt_tokens, outcome.completion_tokens = stats.get("prompt_tokens"), stats.get("completion_tokens")
    except (asyncio.CancelledError, GeneratorExit):
        # Stopped by the user (the stream was closed): keep what was generated in the query log.
        with anyio.CancelScope(shield=True):
            try:
                await _save(session, user_id, question, standalone, asset_tag, started,
                            Outcome(answer="".join(sink), mode="stopped", model=llm.model, prompt_version=prompt_id))
            except Exception as exc:  # the client is gone; logging must not raise
                log.warning("stopped_answer_not_logged", error=type(exc).__name__)
        raise

    query_id = await _save(session, user_id, question, standalone, asset_tag, started, outcome)
    yield {"event": "done", "data": _response(outcome, desired_format, standalone, asset_tag, query_id).model_dump(mode="json")}


def _confidence(outcome: Outcome) -> float:
    scores = [item["score"] for item in outcome.evidence]
    if outcome.refused or not scores:
        return 0.0
    cited = outcome.grounding.cited if outcome.grounding else []
    return max(scores[n - 1] for n in cited) if cited else scores[0]


async def _save(session: AsyncSession, user_id: int, question: str, standalone: str, asset_tag: str,
                started: float, outcome: Outcome) -> int:
    row = QueryLog(
        user_id=user_id, question=question, answer=outcome.answer, mode=outcome.mode, asset_tag=asset_tag,
        confidence=round(_confidence(outcome), 2), latency_ms=round((time.perf_counter() - started) * 1000),
        retrieved_chunk_ids=[item["chunk_id"] for item in outcome.evidence],
        standalone_question=standalone if standalone != question else None, model=outcome.model,
        prompt_version=outcome.prompt_version, evidence_strength=outcome.strength,
        grounding=outcome.grounding.as_dict() if outcome.grounding else None,
        prompt_tokens=outcome.prompt_tokens, completion_tokens=outcome.completion_tokens,
    )
    session.add(row)
    await session.commit()
    return row.id


def _response(outcome: Outcome, desired_format: str, standalone: str, asset_tag: str, query_id: int) -> ChatAnswer:
    return ChatAnswer(
        answer=outcome.answer, mode=outcome.mode, format=desired_format, evidenceStrength=outcome.strength,
        refused=outcome.refused, notice=outcome.notice, warnings=outcome.warnings,
        grounding=outcome.grounding.as_dict() if outcome.grounding else None, question=standalone,
        model=outcome.model, structured=outcome.structured, confidence=round(_confidence(outcome), 2),
        citations=citations(outcome.evidence, outcome.grounding.cited if outcome.grounding else []),
        assetTag=asset_tag, queryId=query_id,
    )
