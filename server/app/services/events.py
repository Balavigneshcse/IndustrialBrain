"""Asset events: dated failures, maintenance actions, measurements and readings found in record
documents (maintenance logs, inspection and incident reports, readings tables), and in dated text of
unclassified documents. Manuals and procedures describe what *could* happen, so they produce none."""
import re
from datetime import date

from .entities import RECORD_TYPES, asset_mentions, find_actions, find_dates, find_failures, find_measurements

_BOUNDARY = re.compile(r"[.!?\n]")


def _sentence_at(text: str, position: int) -> str:
    starts = [m.end() for m in _BOUNDARY.finditer(text, 0, position)]
    start = starts[-1] if starts else 0
    end_match = _BOUNDARY.search(text, position)
    end = end_match.end() if end_match else len(text)
    return " ".join(text[start:end].split())[:300]


def chunk_events(text: str, tags: list[str], document_type: str, fallback_date: str | None,
                 registry: set[str] | None = None) -> list[dict]:
    """Events for one chunk: [{"asset_tag", "event_date", "kind", "label", "value", "unit", "detail"}]."""
    if not tags:
        return []
    if document_type not in RECORD_TYPES and not (document_type == "Industrial Document" and find_dates(text)):
        return []
    if document_type == "Operating Readings":
        return _reading_events(text, registry)

    dates = find_dates(text)
    event_date = dates[0] if dates else fallback_date
    found = [("failure", label, None, None, pos) for label, pos in find_failures(text)]
    found += [("action", label, None, None, pos) for label, pos in find_actions(text)]
    found += [("measurement", m["label"], m["value"], m["unit"], m["start"]) for m in find_measurements(text)]
    return [
        {"asset_tag": tag, "event_date": _as_date(event_date), "kind": kind, "label": label,
         "value": value, "unit": unit, "detail": _sentence_at(text, pos)}
        for tag in tags for kind, label, value, unit, pos in found
    ]


def _reading_events(text: str, registry: set[str] | None) -> list[dict]:
    lines = text.splitlines()
    header = lines[0] if lines else ""
    events = []
    for row in lines[1:]:
        dates = find_dates(row)
        row_tags, _ = asset_mentions(row, registry)
        if dates and row_tags:
            for tag in row_tags:
                events.append({"asset_tag": tag, "event_date": _as_date(dates[0]), "kind": "reading",
                               "label": row[:128], "value": None, "unit": None, "detail": f"{header}\n{row}"[:300]})
    return events


def _as_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
