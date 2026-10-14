"""RCA briefs: written by the language model as schema-validated JSON from the asset's most relevant
evidence, with the extractive brief as fallback. Measurements, event dates and citations always come
from the indexed evidence, not from the model.

Briefs are cached for 15 minutes per (asset, evidence, model, prompt), so the Word export returns the
brief that was just shown instead of generating a different one.
"""
import time

import structlog
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..llm import checks, prompts
from ..llm.client import LLMBusy, LLMUnavailable, get_llm
from ..llm.structured import RcaDraft, StructuredOutputError, generate
from . import store
from .answers import generate_rca
from .qa import BUSY_DETAIL, LLM_OFFLINE

log = structlog.get_logger("rca")

RCA_QUESTION = ("Why did {tag} fail? Root cause, failure symptoms, measurements, inspection findings and "
                "maintenance actions for {tag}.")
RCA_TOKENS = 900
CACHE_SECONDS = 900
CACHE_SIZE = 32
_cache: dict[tuple, tuple[float, dict]] = {}


def _citations(evidence: list[dict], cited: list[int]) -> list[dict]:
    return [{"label": f"S{n}", "cited": n in cited, "source": item["metadata"]["source"],
             "page": item["metadata"]["page"], "excerpt": item["text"][:300], "relevance": round(item["score"], 2)}
            for n, item in enumerate(evidence, 1)]


async def build_rca(session: AsyncSession, tag: str) -> dict:
    settings = get_settings()
    llm = get_llm()
    tag = tag.strip().upper()
    evidence = await store.search(session, RCA_QUESTION.format(tag=tag), tag, limit=settings.llm_context_chunks)
    scores = [item["score"] for item in evidence]
    brief = await run_in_threadpool(generate_rca, tag, evidence)
    brief.update(mode="extractive", model=None, notice=None, warnings=[], grounding=None,
                 evidenceStrength=checks.evidence_strength(scores, None, not evidence),
                 confidence=round(scores[0], 2) if scores else 0.0, citations=_citations(evidence, []))
    if not evidence or not llm.available():
        if evidence and llm.enabled:
            brief["notice"] = LLM_OFFLINE
        return brief

    prompt = prompts.load("rca")
    source_text, used = prompts.source_blocks(evidence, prompts.source_budget_chars(RCA_TOKENS))
    evidence, scores = evidence[:used], scores[:used]
    key = (tag, tuple(item["chunk_id"] for item in evidence), llm.model, prompt.id)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    messages = prompts.grounded_messages(prompt, source_text, f"Write the RCA brief for asset {tag}.")
    try:
        draft, _ = await generate(llm, RcaDraft, messages, max_tokens=RCA_TOKENS, kind="rca")
    except LLMBusy:
        raise HTTPException(429, BUSY_DETAIL, headers={"Retry-After": "30"}) from None
    except (LLMUnavailable, StructuredOutputError) as exc:
        log.warning("rca_generation_failed", tag=tag, error=str(exc))
        brief["notice"] = LLM_OFFLINE if isinstance(exc, LLMUnavailable) else \
            "The model's RCA did not validate; showing the evidence summary."
        return brief

    invalid: list[str] = []

    def clean(text: str) -> str:
        fixed, bad = checks.normalize_citations(text.strip(), len(evidence))
        invalid.extend(b for b in bad if b not in invalid)
        return fixed

    fields = {
        "observedProblem": clean(draft.observedProblem),
        **{name: [clean(item) for item in getattr(draft, name) if item.strip()]
           for name in ("probableCauses", "recordedActions", "recommendedInvestigation", "preventiveActions")},
    }
    facts = [fields["observedProblem"], *fields["probableCauses"], *fields["recordedActions"]]
    advice = [*fields["recommendedInvestigation"], *fields["preventiveActions"]]
    refused = all(checks.is_refusal(cause) for cause in fields["probableCauses"])
    grounding = checks.check("\n".join(facts + advice), [item["text"] for item in evidence], frozenset(advice))
    grounding.invalidCitations = invalid
    brief.update(
        fields, mode="llm", model=llm.model, grounding=grounding.as_dict(), warnings=grounding.warnings(),
        evidenceStrength=checks.evidence_strength(scores, grounding, refused),
        confidence=round(max((scores[n - 1] for n in grounding.cited), default=scores[0]), 2),
        citations=_citations(evidence, grounding.cited),
        disclaimer=(f"Drafted by the {llm.model} language model from the cited records. Check each statement "
                    "against its source and validate with domain experts before acting."),
    )
    if len(_cache) >= CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), brief)
    return brief
