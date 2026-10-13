"""Extractive answers and RCA briefs assembled from retrieved evidence (no language model yet;
Phase 3 of docs/upgrade-plan.md adds one). Pure functions: no database access.

Evidence items are dicts: {"text", "score", "chunk_id", "metadata": {source, page, document_id,
document_type, asset_tags, failures, actions, dates, measurements}} with list fields joined by commas.
"""
import re

GREETING_WORDS = frozenset({
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "howdy", "greetings", "thanks", "thank you", "bye", "goodbye",
    "ok", "okay", "yes", "no", "sure", "yo", "sup",
})

FILE_PATTERN = re.compile(
    r'[\w\-\.]+\.(xlsx|xls|pdf|csv|docx|txt|pptx|json|xml|html|htm|md|eml|msg)',
    re.IGNORECASE,
)

ABOUT_PHRASES = ("tell me about", "what is in", "summarize", "summary of", "describe", "contents of")

# The mode label says what produced the answer instead of claiming "local-model".
ANSWER_MODE = "extractive"
INSUFFICIENT_EVIDENCE = (
    "I could not find sufficient evidence in the indexed industrial documents to answer "
    "this question. Try uploading relevant documents first."
)


def classify_query(question: str) -> str:
    q = question.lower().strip().rstrip("!.,? ")
    if q in GREETING_WORDS or len(q) < 3:
        return "greeting"
    if FILE_PATTERN.search(question):
        return "document"
    if any(p in q for p in ABOUT_PHRASES):
        return "document"
    return "industrial"


def generate_answer(question: str, evidence: list[dict],
                    desired_format: str = "quick_answer") -> tuple[str, str, float]:
    qtype = classify_query(question)

    # Greetings
    if qtype == "greeting":
        return (
            "Hello! I'm IndusMind AI, your industrial intelligence assistant. "
            "You can ask me questions about your uploaded maintenance records, "
            "inspection reports, and equipment manuals. For example, try:\n\n"
            "• *What maintenance was performed on P-101?*\n"
            "• *What are the common failure modes in our records?*\n"
            "• *What safety steps apply before pump maintenance?*",
            "assistant", 1.0,
        )

    if not evidence:  # the relevance threshold is applied by the caller (settings.min_evidence_score)
        return INSUFFICIENT_EVIDENCE, ANSWER_MODE, 0.0

    # Extract entities from primary evidence only to avoid cross-contamination
    failures, actions, measurements, sources = set(), set(), set(), set()
    primary_source = evidence[0]["metadata"].get("source", "")
    for item in evidence:
        meta = item["metadata"]
        if meta.get("source", "") == primary_source:
            failures.update(filter(None, meta.get("failures", "").split(",")))
            actions.update(filter(None, meta.get("actions", "").split(",")))
            measurements.update(filter(None, meta.get("measurements", "").split(",")))
        sources.add(meta.get("source", ""))

    # Heuristic score, not a calibrated probability (replaced by evidence strength in Phase 3).
    confidence = min(0.94, 0.55 + len(evidence) * 0.035 + evidence[0]["score"] * 0.22)
    q_lower = question.lower()
    is_about = any(w in q_lower for w in ABOUT_PHRASES)

    # Document summary queries
    if is_about or qtype == "document":
        source_label = ", ".join(sorted(sources)) if sources else "the uploaded document"
        clean_blocks = []
        for item in evidence:
            text = item["text"].strip()
            if text and text not in clean_blocks:
                clean_blocks.append(text)
        if clean_blocks:
            intro = f"Here is an overview of **{source_label}**:\n\n"
            summary_text = " ".join(" ".join(b.split()) for b in clean_blocks[:2])
            if len(summary_text) > 600:
                summary_text = summary_text[:600] + "..."
            body = f"The document contains records and data structured as follows:\n\n> {summary_text}"
            if failures or actions:
                extras = []
                if failures:
                    extras.append(f"* **Detected Failure Modes**: {', '.join(sorted(failures))}")
                if actions:
                    extras.append(f"* **Recorded Maintenance Actions**: {', '.join(sorted(actions))}")
                body += "\n\n**Operational Highlights**:\n" + "\n".join(extras)
            return intro + body, ANSWER_MODE, confidence

    # Format-specific answers
    if desired_format == "table":
        rows = [
            "| Field | Extracted Evidence |",
            "| --- | --- |",
            f"| Failures | {', '.join(sorted(failures)) or 'None detected'} |",
            f"| Actions | {', '.join(sorted(actions)) or 'None detected'} |",
            f"| Measurements | {', '.join(sorted(measurements)[:5]) or 'None detected'} |",
            f"| Top Evidence | {evidence[0]['text'][:200].strip()}… |",
        ]
        return "\n".join(rows), ANSWER_MODE, confidence

    if desired_format == "bullet" or desired_format == "checklist":
        if failures or actions:
            return (
                f"Here is a bulleted summary of operational findings:\n\n"
                f"* **Observed Failure Modes**: {', '.join(sorted(failures)) or 'None observed'}\n"
                f"* **Maintenance Actions**: {', '.join(sorted(actions)) or 'None recorded'}\n"
                f"* **Key Measurements**: {', '.join(sorted(measurements)[:5]) or 'N/A'}",
                ANSWER_MODE, confidence,
            )
        lines = [f"Here are key points from **{', '.join(sorted(sources)) or 'the document'}**:\n"]
        for item in evidence[:4]:
            lines.append(f"* {' '.join(item['text'].split())}")
        return "\n".join(lines), ANSWER_MODE, confidence

    if desired_format == "work_order":
        return (
            f"**Work Order**\n"
            f"- **Problem**: {', '.join(sorted(failures)) or 'Reported issue'}\n"
            f"- **Recommended Action**: {', '.join(sorted(actions)) or 'Inspect asset'}\n"
            f"- **Priority**: High\n"
            f"- **Evidence**: {evidence[0]['text'][:250].strip()}",
            ANSWER_MODE, confidence,
        )

    if desired_format == "report":
        return (
            f"### Technical Root Cause & Evidence Report\n"
            f"- **Identified Failure Modes**: {', '.join(sorted(failures)) or 'None detected'}\n"
            f"- **Recommended Corrective Actions**: {', '.join(sorted(actions)) or 'Standard inspection'}\n"
            f"- **Primary Evidence**: {evidence[0]['text'][:350].strip()}",
            ANSWER_MODE, confidence,
        )

    # Default quick_answer
    if failures and any(w in q_lower for w in ["why", "fail", "cause"]):
        return (
            f"Based on the indexed maintenance records, observed failure modes include: "
            f"{', '.join(sorted(failures))}. Key corrective actions: "
            f"{', '.join(sorted(actions)) or 'Standard inspection procedures'}.",
            ANSWER_MODE, confidence,
        )
    parts = []
    if failures:
        parts.append("Observed failure patterns include: " + ", ".join(sorted(failures)) + ".")
    if actions:
        parts.append("Recorded maintenance actions include: " + ", ".join(sorted(actions)) + ".")
    if measurements:
        parts.append("Relevant measurements include: " + ", ".join(sorted(measurements)[:8]) + ".")
    if not parts:
        parts.append(evidence[0]["text"][:450].strip())
    else:
        parts.append("Primary evidence: " + evidence[0]["text"][:350].strip())
    return " ".join(parts), ANSWER_MODE, confidence


def generate_rca(tag: str, evidence: list[dict]) -> dict:
    failures, actions, dates, measurements = set(), set(), set(), set()
    citations = []
    for item in evidence:
        meta = item["metadata"]
        failures.update(filter(None, meta.get("failures", "").split(",")))
        actions.update(filter(None, meta.get("actions", "").split(",")))
        dates.update(filter(None, meta.get("dates", "").split(",")))
        measurements.update(filter(None, meta.get("measurements", "").split(",")))
        citations.append({
            "source": meta.get("source", ""),
            "page": meta.get("page", 1),
            "excerpt": item["text"][:300],
            "relevance": round(item.get("score", 0.5), 2),
        })

    failure_list = sorted(failures)
    action_list = sorted(actions)

    problem = (
        f"Asset {tag.upper()} exhibits recurring issues: {', '.join(failure_list)}."
        if failure_list else f"Asset {tag.upper()} requires investigation based on available evidence."
    )

    investigation = [
        "Perform detailed vibration analysis to identify imbalance or misalignment",
        "Inspect bearing condition and lubrication quality",
        "Review maintenance history for recurring patterns",
        "Check sensor calibration and operating parameter trends",
    ]
    preventive = [
        "Implement condition-based monitoring programme",
        "Review and update maintenance schedule intervals",
        "Ensure proper lubrication procedures are followed",
        "Train operators on early warning sign recognition",
    ]

    return {
        "assetTag": tag.upper(),
        "observedProblem": problem,
        "probableCauses": failure_list or ["Insufficient evidence to determine root cause"],
        "recordedActions": action_list or ["No corrective actions recorded"],
        "measurements": sorted(measurements)[:10],
        "eventDates": sorted(dates)[:10],
        "recommendedInvestigation": investigation,
        "preventiveActions": preventive,
        "confidence": min(0.92, 0.4 + len(evidence) * 0.06),
        "disclaimer": "This RCA is auto-generated from indexed evidence. Validate with domain experts before action.",
        "citations": citations[:6],
    }
