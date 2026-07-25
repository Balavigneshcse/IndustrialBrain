from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request
from .config import settings
from .local_llm import local_llm_instance


def generate_answer(question: str, evidence: list[dict]) -> tuple[str, str]:
    if settings.local_llm_enabled:
        local_llm_instance.load_model(settings.local_llm_path)
        if local_llm_instance.is_loaded:
            answer = _local_llm(question, evidence)
            if answer:
                return answer, "local-model"
    elif settings.gemini_api_key:
        answer = _gemini(question, evidence)
        if answer:
            return answer, "gemini"
    return _offline_answer(question, evidence), "offline-evidence"

def _local_llm(question: str, evidence: list[dict]) -> str:
    context = "\n\n".join(
        f"[Source {index}: {item['metadata']['source']}, page {item['metadata']['page']}]\n{item['text']}"
        for index, item in enumerate(evidence, start=1)
    )
    prompt = f"""You are an industrial knowledge copilot. Answer concisely in 1-2 sentences using only the supplied evidence.

### Question:
{question}

### Evidence:
{context}

### Answer:
"""
    return local_llm_instance.generate(prompt)


def _gemini(question: str, evidence: list[dict]) -> str:
    context = "\n\n".join(
        f"[Source {index}: {item['metadata']['source']}, page {item['metadata']['page']}]\n{item['text']}"
        for index, item in enumerate(evidence, start=1)
    )
    prompt = f"""You are an industrial knowledge copilot. Answer only from the supplied evidence.
If the evidence is insufficient, say that clearly. Do not invent measurements, causes, or dates.
Give a concise answer followed by a short evidence-based explanation. Citations are shown separately by the UI.

Question: {question}

Evidence:
{context}
"""
    model = urllib.parse.quote(settings.gemini_model, safe="")
    key = urllib.parse.quote(settings.gemini_api_key, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 700}
    }).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError):
        return ""


def _offline_answer(question: str, evidence: list[dict]) -> str:
    if not evidence or evidence[0]["score"] < 0.05:
        return "I could not find sufficient evidence in the indexed industrial documents to answer this question."
    failures, actions, measurements = set(), set(), set()
    for item in evidence:
        meta = item["metadata"]
        failures.update(filter(None, meta.get("failures", "").split(",")))
        actions.update(filter(None, meta.get("actions", "").split(",")))
        measurements.update(filter(None, meta.get("measurements", "").split(",")))
    parts = ["The indexed records indicate the following evidence:"]
    if failures:
        parts.append("Observed failure patterns include " + ", ".join(sorted(failures)) + ".")
    if actions:
        parts.append("Recorded maintenance actions include " + ", ".join(sorted(actions)) + ".")
    if measurements:
        parts.append("Relevant measurements include " + ", ".join(sorted(measurements)[:8]) + ".")
    parts.append("The strongest matching passage states: " + evidence[0]["text"][:450].strip())
    return " ".join(parts)


def generate_rca(tag: str, evidence: list[dict]) -> dict:
    failures, actions, dates, measurements = set(), set(), set(), set()
    for item in evidence:
        meta = item["metadata"]
        failures.update(filter(None, meta.get("failures", "").split(",")))
        actions.update(filter(None, meta.get("actions", "").split(",")))
        dates.update(filter(None, meta.get("dates", "").split(",")))
        measurements.update(filter(None, meta.get("measurements", "").split(",")))
    failure_text = ", ".join(sorted(failures)) or "No explicit failure category extracted"
    likely_causes = []
    if "bearing wear" in failures or "bearing failure" in failures:
        likely_causes.extend(["Lubrication quality or interval", "Shaft alignment", "Excess vibration or load"])
    if "overheating" in failures:
        likely_causes.append("Cooling, lubrication, or operating-load condition")
    if "cavitation" in failures:
        likely_causes.append("Insufficient suction head or restricted inlet")
    if not likely_causes:
        likely_causes = ["Review operating conditions and the highest-ranked source passages"]
    confidence = min(0.94, 0.45 + len(evidence) * 0.06 + len(failures) * 0.05)
    return {
        "assetTag": tag.upper(),
        "observedProblem": failure_text,
        "probableCauses": list(dict.fromkeys(likely_causes)),
        "recordedActions": sorted(actions),
        "measurements": sorted(measurements),
        "eventDates": sorted(dates),
        "recommendedInvestigation": [
            "Validate the timeline against the cited maintenance and inspection records.",
            "Inspect lubrication condition, alignment, vibration trend, and operating envelope.",
            "Confirm corrective actions were closed and verify recurrence after each intervention.",
        ],
        "preventiveActions": [
            "Introduce condition-based vibration and temperature checks.",
            "Track recurring failure modes by asset and maintenance action.",
            "Require evidence-linked closure notes after corrective maintenance.",
        ],
        "confidence": round(confidence, 2),
        "disclaimer": "Decision-support analysis based on uploaded records; engineering verification is required.",
    }

