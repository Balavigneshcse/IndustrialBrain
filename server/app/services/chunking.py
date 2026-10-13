"""Structure-aware chunking.

Text is split into sections at headings ("Findings:", ALL-CAPS titles, Markdown "#") and at lines
that start with a date, so each entry of a maintenance log becomes its own chunk with its own date.
Small non-entry sections (titles, short preambles) are merged into the section that follows;
dated entries are never merged with each other. Long sections are cut into overlapping windows.
Sizes are in words (roughly 0.75 of a model token).
"""
import re

from .entities import DATE_REGEX

DATE_LINE = re.compile(rf"^\s*(?:{DATE_REGEX})\b", re.IGNORECASE)
TARGET_WORDS = 300
OVERLAP_WORDS = 45
MIN_WORDS = 40


def _is_heading(line: str) -> bool:
    words = line.split()
    if not words or len(words) > 8:
        return False
    return line.startswith("#") or line.endswith(":") or (line.isupper() and any(c.isalpha() for c in line))


def split_sections(text: str) -> list[dict]:
    """[{"heading", "text", "entry"}] where entry=True for sections that start with a date line."""
    sections: list[dict] = []
    current = {"heading": "", "lines": [], "entry": False}

    def flush():
        body = " ".join(" ".join(current["lines"]).split())
        if body:
            sections.append({"heading": current["heading"], "text": body, "entry": current["entry"]})

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        starts_entry = bool(DATE_LINE.match(line))
        if (starts_entry or _is_heading(line)) and current["lines"]:
            flush()
            current = {"heading": line.rstrip(":")[:200], "lines": [], "entry": starts_entry}
        elif not current["lines"]:
            current.update(heading=line.rstrip(":")[:200] if (starts_entry or _is_heading(line)) else "",
                           entry=starts_entry)
        current["lines"].append(line)
    flush()
    return sections


def _merge_small(sections: list[dict]) -> list[dict]:
    merged: list[dict] = []
    carry: dict | None = None
    for section in sections:
        if carry is not None:
            section = {**section, "text": f"{carry['text']} {section['text']}",
                       "heading": section["heading"] or carry["heading"]}
            carry = None
        if not section["entry"] and len(section["text"].split()) < MIN_WORDS:
            carry = section
            continue
        merged.append(section)
    if carry is not None:
        merged.append(carry)  # a short trailing section (e.g. a conclusion) stays on its own
    return merged


def _windows(words: list[str]) -> list[str]:
    if len(words) <= TARGET_WORDS:
        return [" ".join(words)]
    step = TARGET_WORDS - OVERLAP_WORDS
    return [" ".join(words[start:start + TARGET_WORDS])
            for start in range(0, max(1, len(words) - OVERLAP_WORDS), step)]


def chunk_table(pages: list[dict]) -> list[dict]:
    """Tables (CSV/XLSX rows): groups of rows, each chunk repeating the header row for context."""
    chunks = []
    for page in pages:
        lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
        if not lines:
            continue
        header, rows = lines[0], lines[1:] or lines[:1]
        groups: list[list[str]] = [[]]
        for row in rows:
            if groups[-1] and len(" ".join(groups[-1] + [row]).split()) > TARGET_WORDS:
                groups.append([])
            groups[-1].append(row)
        for group in groups:
            text = "\n".join([header, *group])  # keep rows on their own lines for event extraction
            chunks.append({"page": page["page"], "section": header[:200], "text": text, "words": len(text.split())})
    return chunks


def chunk_pages(pages: list[dict], tabular: bool = False) -> list[dict]:
    """[{"page", "section", "text", "words"}] in document order."""
    if tabular:
        return chunk_table(pages)
    chunks = []
    for page in pages:
        for section in _merge_small(split_sections(page["text"])):
            for text in _windows(section["text"].split()):
                chunks.append({"page": page["page"], "section": section["heading"], "text": text,
                               "words": len(text.split())})
    return chunks
