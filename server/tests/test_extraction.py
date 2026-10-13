"""Unit tests: file-format extraction, entities, chunking, events and embeddings (no database)."""
from pathlib import Path

import pytest

from server.app.services.chunking import chunk_pages
from server.app.services.entities import asset_mentions, classify_document, extract_entities, find_dates
from server.app.services.events import chunk_events
from server.app.services.extraction import extract_text
from server.app.services.uploads import file_type_problem

SAMPLES = Path(__file__).resolve().parents[2] / "sample-data"


def sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


# ── File formats ─────────────────────────────────────────────────────────────
def test_empty_file_raises_instead_of_indexing(tmp_path: Path):
    empty = tmp_path / "blank.txt"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="No readable text"):
        extract_text(empty)


def test_corrupt_docx_raises_instead_of_indexing_error_text(tmp_path: Path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"PK\x03\x04 this is not a real zip archive")
    with pytest.raises(ValueError, match="DOCX extraction failed"):
        extract_text(broken)


@pytest.mark.parametrize("name,head,ok", [
    ("report.pdf", b"%PDF-1.7 ...", True),
    ("report.pdf", b"MZ\x90\x00 an executable", False),
    ("notes.txt", b"plain text", True),
    ("notes.txt", b"\x00\x01binary", False),
    ("tool.exe", b"MZ", False),
    ("sheet.xlsx", b"PK\x03\x04", True),
])
def test_upload_type_allow_list_checks_content(name, head, ok):
    assert (file_type_problem(name, head) is None) is ok


# ── Entities ─────────────────────────────────────────────────────────────────
def test_negated_asset_mention_is_not_a_subject():
    subject, negated = asset_mentions(sample("compressor-c201-maintenance.txt"))
    assert subject == ["C-201"] and negated == ["P-101"]


@pytest.mark.parametrize("text,expected", [
    ("Pipe DN50 flange PN16, motor IP65, bolt M12", []),
    ("REV 12 dated UTC 2025, ID 4471", []),
    ("Asset family: P-100 series centrifugal pump", []),
    ("Pump P101 and motor M-201", ["M-201", "P-101"]),
])
def test_codes_that_only_look_like_tags_are_ignored(text, expected):
    assert extract_entities(text)["asset_tags"] == expected


def test_registry_limits_recognised_tags():
    assert asset_mentions("Pump P-101 and tank T-900", registry={"P-101"})[0] == ["P-101"]


def test_negated_failures_and_partial_words_are_not_matched():
    entities = extract_entities("No cavitation observed. Shaft was misaligned; the pump was not tested.")
    assert entities["failures"] == ["misalignment"]
    assert entities["actions"] == []  # "misaligned" is not "aligned"; "not tested" is negated


def test_ids_and_codes_are_not_measurements():
    assert extract_entities("Ref e3f-5926c-41 and P-101 C at 92 C")["measurements"] == ["92 C"]


def test_measurements_with_separators_and_percent():
    assert extract_entities("Speed 2,950 rpm, efficiency 85%, vibration 8.2 mm/s")["measurements"] == \
        ["2950 rpm", "85%", "8.2 mm/s"]


def test_dates_are_iso_and_day_first():
    assert find_dates("On 12-Jan-2025, 3/4/2025, 25/12/2024 and Jan 5, 2026") == \
        ["2025-01-12", "2025-04-03", "2024-12-25", "2026-01-05"]


@pytest.mark.parametrize("name,expected", [
    ("pump-p101-oem-manual.txt", "Equipment Manual"),
    ("safety-sop.txt", "Standard Operating Procedure"),
    ("pump-p101-maintenance-history.txt", "Maintenance Record"),
    ("pump-p101-inspection-report.txt", "Inspection Report"),
    ("operating-readings.csv", "Operating Readings"),
    ("compressor-c201-maintenance.txt", "Maintenance Record"),
])
def test_sample_documents_are_classified_correctly(name, expected):
    assert classify_document(name, sample(name)) == expected


# ── Chunking and events ──────────────────────────────────────────────────────
def test_maintenance_log_entries_become_separate_chunks():
    chunks = chunk_pages([{"page": 2, "text": sample("pump-p101-maintenance-history.txt")}])
    assert [c["section"] for c in chunks] == ["12-Jan-2025", "18-Mar-2025", "04-Jul-2025", "22-Nov-2025",
                                              "Maintenance conclusion"]
    assert all(c["page"] == 2 for c in chunks)


def test_long_sections_are_windowed_with_overlap():
    chunks = chunk_pages([{"page": 1, "text": " ".join(f"w{i}" for i in range(700))}])
    assert [c["words"] for c in chunks] == [300, 300, 190]
    assert chunks[1]["text"].split()[0] == "w255"  # 45 words of overlap


def test_tables_keep_the_header_on_every_chunk():
    rows = "\n".join(["date | tag | value"] + [f"2025-01-{d:02d} | P-101 | {d}" for d in range(1, 29)] * 10)
    chunks = chunk_pages([{"page": 1, "text": rows}], tabular=True)
    assert len(chunks) > 1 and all(c["text"].startswith("date | tag | value\n") for c in chunks)


def test_events_are_dated_per_log_entry_and_only_from_records():
    entry = "22-Nov-2025 Pump P-101 was stopped after vibration reached 8.2 mm/s. The team replaced the bearing."
    events = chunk_events(entry, ["P-101"], "Maintenance Record", None)
    assert {(e["kind"], e["label"], str(e["event_date"])) for e in events} >= {
        ("action", "replaced", "2025-11-22"), ("measurement", "8.2 mm/s", "2025-11-22")}
    assert chunk_events(entry, ["P-101"], "Equipment Manual", None) == []
    assert chunk_events(entry, ["P-101"], "Industrial Document", None)  # dated text of an unclassified note
    assert chunk_events("Pump P-101 bearing replaced.", ["P-101"], "Industrial Document", None) == []


# ── Embeddings ───────────────────────────────────────────────────────────────
def test_embeddings_are_384_dim_and_normalized():
    from server.app.services.models import embed_query

    vector = embed_query("pump bearing vibration")
    assert len(vector) == 384
    assert abs(sum(x * x for x in vector) ** 0.5 - 1.0) < 1e-3
