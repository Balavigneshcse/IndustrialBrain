"""Versioned prompts and prompt assembly.

Prompt files live in llm/prompts/<name>.v<N>.md. The highest version is used, and its id
("answer.v1") is stored with every logged answer, so a prompt change can be compared in the eval.
"""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..core.config import get_settings

PROMPT_DIR = Path(__file__).with_name("prompts")

# Chat-template control tokens and our own source delimiters must not appear inside document text:
# a document could otherwise close its <source> block or open a new chat turn (prompt injection).
CONTROL = re.compile(r"<\|[^|>\n]{1,40}\|>|</?\s*source\b[^>]*>|<\s*/?\s*(?:system|user|assistant)\s*>", re.IGNORECASE)
CHARS_PER_TOKEN = 3.2      # conservative for technical English with numbers and tags
PROMPT_OVERHEAD = 700      # tokens for the system prompt, question and chat template

FORMATS = {
    "quick_answer": "Format: one to three short paragraphs, at most about 150 words.",
    "paragraph": "Format: one to three short paragraphs, at most about 150 words.",
    "bullet": "Format: a short markdown bullet list (at most 8 bullets). Each bullet states one fact and ends with its citation.",
    "table": ("Format: a markdown table with a header row. Put the citations in the last column of each row. "
              "Add one sentence after the table only if something must be said that does not fit in it."),
    "report": ("Format: markdown with the headings ### Findings, ### Evidence and ### Gaps. "
               "Under Gaps, list what the sources do not cover."),
}
STRUCTURED_FORMATS = ("work_order", "checklist")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.name}.v{self.version}"


@lru_cache
def load(name: str) -> Prompt:
    versions = {int(path.stem.rsplit(".v", 1)[1]): path for path in PROMPT_DIR.glob(f"{name}.v*.md")}
    if not versions:
        raise FileNotFoundError(f"no prompt file {name}.v<N>.md in {PROMPT_DIR}")
    version = max(versions)
    return Prompt(name, version, versions[version].read_text(encoding="utf-8").strip())


def clean_text(text: str) -> str:
    return CONTROL.sub(" ", text)


def source_budget_chars(max_answer_tokens: int) -> int:
    return int((get_settings().llm_num_ctx - max_answer_tokens - PROMPT_OVERHEAD) * CHARS_PER_TOKEN)


def source_blocks(evidence: list[dict], budget_chars: int) -> tuple[str, int]:
    """Numbered <source id="S1" ...> blocks that fit the budget. Returns (text, number of sources used);
    the caller keeps only that many evidence items so citation numbers match."""
    blocks: list[str] = []
    used = 0
    for number, item in enumerate(evidence, 1):
        meta = item["metadata"]
        attributes = [f'id="S{number}"', f'document="{_attr(meta.get("source", ""))}"', f'page="{meta.get("page", 1)}"']
        if meta.get("section"):
            attributes.append(f'section="{_attr(meta["section"])[:120]}"')
        header = f"<source {' '.join(attributes)}>"
        room = budget_chars - used - len(header) - 12
        if room < 200:
            break
        body = "\n".join(" ".join(line.split()) for line in clean_text(item["text"]).splitlines() if line.strip())
        if len(body) > room:
            body = body[:room].rsplit(" ", 1)[0] + " …"
        block = f"{header}\n{body}\n</source>"
        blocks.append(block)
        used += len(block) + 2
    return "\n\n".join(blocks), len(blocks)


def _attr(value: str) -> str:
    return clean_text(str(value)).replace('"', "'").replace("\n", " ")


# Repeated after the question: a small model follows the rules it read last most reliably.
REMINDER = ("Answer only what was asked, briefly, from the sources above. Cite every fact like [S1]. Copy numbers "
            "exactly. State causes and conclusions only as the sources state them; do not rule a cause in or out "
            "yourself.")


def grounded_messages(prompt: Prompt, sources: str, question: str, desired_format: str = "") -> list[dict]:
    system = prompt.text.replace("{{format}}", FORMATS.get(desired_format, FORMATS["quick_answer"]))
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Sources:\n{sources}\n\nQuestion: {clean_text(question)}\n\n({REMINDER})"}]


def rewrite_messages(turns: list[tuple[str, str]], question: str) -> list[dict]:
    conversation = "\n".join(f"{'User' if role == 'user' else 'Assistant'}: {clean_text(text)}" for role, text in turns)
    return [{"role": "system", "content": load("rewrite").text},
            {"role": "user", "content": f"Conversation:\n{conversation}\n\nLatest message: {clean_text(question)}\n\n"
                                        "Standalone question:"}]
