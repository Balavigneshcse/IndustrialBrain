"""RAG Service — ChromaDB vector store, query classification, evidence synthesis."""
from __future__ import annotations
import hashlib
import math
import re
from collections import Counter
from pathlib import Path

from ..config import settings

VECTOR_SIZE = 384
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]{2,}")

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


# ── Embedding ────────────────────────────────────────────────────────
def embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    tokens = TOKEN_PATTERN.findall(text.lower())
    for token, count in Counter(tokens).items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def chunk_pages(pages: list[dict], size: int = 900, overlap: int = 150) -> list[dict]:
    chunks = []
    for page in pages:
        text = " ".join(page["text"].split())
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                split = text.rfind(" ", start, end)
                if split > start + size // 2:
                    end = split
            content = text[start:end].strip()
            if content:
                chunks.append({"page": page["page"], "text": content})
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


# ── RAG Service ──────────────────────────────────────────────────────
class RAGService:
    def __init__(self):
        self._collection = None
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            chroma_path = Path(settings.CHROMA_PATH)
            chroma_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                "industrial_knowledge", metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"[RAG] ChromaDB init failed: {e}")

    @property
    def ready(self) -> bool:
        return self._collection is not None

    def count(self) -> int:
        return self._collection.count() if self._collection else 0

    # ── Indexing ─────────────────────────────────────────────────────
    def index_document(self, document_id: str, name: str, chunks: list[dict],
                       entities: dict, doc_type: str) -> int:
        if not self._collection or not chunks:
            return 0
        # Remove old chunks for this document
        try:
            old = self._collection.get(where={"document_id": document_id})
            if old.get("ids"):
                self._collection.delete(ids=old["ids"])
        except Exception:
            pass

        ids, docs, embeds, metas = [], [], [], []
        for i, chunk in enumerate(chunks):
            ids.append(f"{document_id}-{i}")
            docs.append(chunk["text"])
            embeds.append(embedding(chunk["text"]))
            metas.append({
                "document_id": document_id,
                "source": name,
                "page": int(chunk["page"]),
                "asset_tags": ",".join(entities.get("asset_tags", [])),
                "failures": ",".join(entities.get("failures", [])),
                "actions": ",".join(entities.get("actions", [])),
                "dates": ",".join(entities.get("dates", [])),
                "measurements": ",".join(entities.get("measurements", [])),
                "document_type": doc_type,
            })
        self._collection.add(ids=ids, documents=docs, embeddings=embeds, metadatas=metas)
        return len(ids)

    def delete_document(self, document_id: str) -> None:
        if not self._collection:
            return
        try:
            old = self._collection.get(where={"document_id": document_id})
            if old.get("ids"):
                self._collection.delete(ids=old["ids"])
        except Exception:
            pass

    # ── Search ───────────────────────────────────────────────────────
    def search(self, question: str, asset_tag: str = "", limit: int = 5) -> list[dict]:
        if not self._collection:
            return []
        query = embedding(f"{question} {asset_tag}")
        where = {"asset_tags": {"$contains": asset_tag.upper()}} if asset_tag else None
        try:
            result = self._collection.query(
                query_embeddings=[query], n_results=limit, where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            result = self._collection.query(
                query_embeddings=[query], n_results=limit,
                include=["documents", "metadatas", "distances"],
            )
        items = []
        for text, meta, dist in zip(
            result.get("documents", [[]])[0],
            result.get("metadatas", [[]])[0],
            result.get("distances", [[]])[0],
        ):
            if asset_tag and asset_tag.upper() not in meta.get("asset_tags", ""):
                continue
            items.append({"text": text, "metadata": meta, "score": round(max(0, 1 - dist), 4)})

        # Check if query asks about a specific file by filename or extension
        q_lower = question.lower()
        if any(ext in q_lower for ext in [".xlsx", ".xls", ".pdf", ".docx", ".csv", ".pptx", ".txt", ".html", ".eml", ".md"]) or "about " in q_lower or "summarize " in q_lower:
            try:
                all_data = self._collection.get(include=["documents", "metadatas"])
                file_items = []
                for text, meta in zip(all_data.get("documents", []), all_data.get("metadatas", [])):
                    src = meta.get("source", "").lower()
                    if src and (src in q_lower or any(w in src for w in q_lower.replace("(", " ").replace(")", " ").split() if len(w) > 4 and w in src)):
                        file_items.append({"text": text, "metadata": meta, "score": 0.95})
                # Prepend matching file items and deduplicate by text
                seen = set()
                combined = []
                for item in file_items + items:
                    t = item["text"]
                    if t not in seen:
                        seen.add(t)
                        combined.append(item)
                items = combined
            except Exception:
                pass

        return items[:limit]

    def search_by_source(self, name_fragment: str, limit: int = 5) -> list[dict]:
        if not self._collection:
            return []
        name_lower = name_fragment.lower().strip()
        if not name_lower:
            return []
        all_data = self._collection.get(include=["documents", "metadatas"])
        items = []
        for text, meta in zip(all_data.get("documents", []), all_data.get("metadatas", [])):
            if name_lower in meta.get("source", "").lower():
                items.append({"text": text, "metadata": meta, "score": 0.85})
        return items[:limit]

    def asset_evidence(self, tag: str) -> list[dict]:
        if not self._collection:
            return []
        tag = tag.upper()
        try:
            result = self._collection.get(
                where={"asset_tags": {"$contains": tag}},
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
        return [
            {"text": t, "metadata": m, "score": 1.0}
            for t, m in zip(result.get("documents", []), result.get("metadatas", []))
        ]

    def all_records(self) -> list[dict]:
        if not self._collection:
            return []
        result = self._collection.get(include=["metadatas"])
        return [{"metadata": m} for m in result.get("metadatas", [])]

    # ── Query Classification ─────────────────────────────────────────
    def classify_query(self, question: str) -> str:
        q = question.lower().strip().rstrip("!.,? ")
        if q in GREETING_WORDS or len(q) < 3:
            return "greeting"
        if FILE_PATTERN.search(question):
            return "document"
        if any(p in q for p in ABOUT_PHRASES):
            return "document"
        return "industrial"

    # ── Answer Generation ────────────────────────────────────────────
    def generate_answer(self, question: str, evidence: list[dict],
                        desired_format: str = "quick_answer") -> tuple[str, str, float]:
        qtype = self.classify_query(question)

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

        # Filename-based search if question mentions a document
        if qtype == "document":
            file_match = FILE_PATTERN.search(question)
            if file_match:
                source_results = self.search_by_source(file_match.group(0))
                if source_results:
                    evidence = source_results

        # No evidence → try partial name match
        if not evidence or evidence[0]["score"] < 0.01:
            # Try long words as document name fragments
            name_pat = re.compile(r'[A-Za-z0-9][\w\-]{4,}[\w]')
            skip = {"about", "which", "where", "there", "their", "these", "those",
                    "should", "would", "could", "maintenance", "performed",
                    "inspection", "question", "tell", "what", "have", "been"}
            for name in name_pat.findall(question):
                if len(name) > 5 and name.lower() not in skip:
                    source_results = self.search_by_source(name)
                    if source_results:
                        evidence = source_results
                        break

        if not evidence or evidence[0]["score"] < 0.01:
            return (
                "I could not find sufficient evidence in the indexed industrial "
                "documents to answer this question. Try uploading relevant documents first.",
                "local-model", 0.0,
            )

        # Extract entities from evidence
        failures, actions, measurements, sources = set(), set(), set(), set()
        for item in evidence:
            meta = item["metadata"]
            failures.update(filter(None, meta.get("failures", "").split(",")))
            actions.update(filter(None, meta.get("actions", "").split(",")))
            measurements.update(filter(None, meta.get("measurements", "").split(",")))
            sources.add(meta.get("source", ""))

        confidence = min(0.94, 0.55 + len(evidence) * 0.035 + evidence[0]["score"] * 0.22)

        # Document summary queries
        q_lower = question.lower()
        is_about = any(w in q_lower for w in ABOUT_PHRASES) or qtype == "document"
        if is_about or (not failures and not actions and not measurements):
            source_label = ", ".join(sorted(sources)) if sources else "the uploaded document"
            snippets = [item["text"][:400].strip() for item in evidence[:3] if item["text"].strip()]
            if snippets:
                intro = f"Here is a summary of **{source_label}**:\n\n"
                body = "\n\n".join(f"> {s}" for s in snippets)
                if failures or actions:
                    extras = []
                    if failures:
                        extras.append(f"**Detected failure patterns**: {', '.join(sorted(failures))}")
                    if actions:
                        extras.append(f"**Recorded actions**: {', '.join(sorted(actions))}")
                    body += "\n\n" + " | ".join(extras)
                return intro + body, "local-model", confidence

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
            return "\n".join(rows), "local-model", confidence

        if desired_format == "checklist":
            return (
                f"1. Inspect asset for failures: {', '.join(sorted(failures)) or 'None observed'}\n"
                f"2. Verify maintenance actions taken: {', '.join(sorted(actions)) or 'None recorded'}\n"
                f"3. Check readings against baseline: {', '.join(sorted(measurements)[:5]) or 'N/A'}",
                "local-model", confidence,
            )

        if desired_format == "work_order":
            return (
                f"**Work Order**\n"
                f"- **Problem**: {', '.join(sorted(failures)) or 'Reported issue'}\n"
                f"- **Recommended Action**: {', '.join(sorted(actions)) or 'Inspect asset'}\n"
                f"- **Priority**: High\n"
                f"- **Evidence**: {evidence[0]['text'][:250].strip()}",
                "local-model", confidence,
            )

        if desired_format == "report":
            return (
                f"### Technical Root Cause & Evidence Report\n"
                f"- **Identified Failure Modes**: {', '.join(sorted(failures)) or 'None detected'}\n"
                f"- **Recommended Corrective Actions**: {', '.join(sorted(actions)) or 'Standard inspection'}\n"
                f"- **Primary Evidence**: {evidence[0]['text'][:350].strip()}",
                "local-model", confidence,
            )

        # Default quick_answer
        if failures and any(w in q_lower for w in ["why", "fail", "cause"]):
            return (
                f"Based on the indexed maintenance records, observed failure modes include: "
                f"{', '.join(sorted(failures))}. Key corrective actions: "
                f"{', '.join(sorted(actions)) or 'Standard inspection procedures'}.",
                "local-model", confidence,
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
        return " ".join(parts), "local-model", confidence

    # ── RCA Generation ───────────────────────────────────────────────
    def generate_rca(self, tag: str, evidence: list[dict]) -> dict:
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


# Singleton instance
rag = RAGService()
