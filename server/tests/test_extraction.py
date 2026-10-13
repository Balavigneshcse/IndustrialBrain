from pathlib import Path

import pytest

from server.services.extraction import classify_document, extract_entities, extract_text
from server.services.rag_service import chunk_pages, embedding, has_asset_tag


def test_entity_extraction():
    text = "On 12-Jun-2025 Pump P-101 showed high vibration at 8.2 mm/s and bearing wear."
    entities = extract_entities(text)
    assert "P-101" in entities["asset_tags"]
    assert "bearing wear" in entities["failures"]


def test_embedding_is_normalized():
    vector = embedding("pump bearing vibration")
    norm = sum(x * x for x in vector) ** 0.5
    assert abs(norm - 1.0) < 0.0001


def test_chunks_keep_page():
    chunks = chunk_pages([{"page": 3, "text": "A " * 1000}], size=200, overlap=20)
    assert len(chunks) > 1
    assert all(item["page"] == 3 for item in chunks)


def test_document_classification():
    assert classify_document("inspection.pdf", "pump data") == "Inspection Report"


def test_asset_tag_match_is_exact():
    meta = {"asset_tags": "P-100,P-101"}
    assert has_asset_tag(meta, "p-101")
    assert not has_asset_tag(meta, "P-10")
    assert not has_asset_tag(meta, "P-1")


def test_empty_file_raises_instead_of_indexing(tmp_path: Path):
    empty = tmp_path / "blank.txt"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="No readable text"):
        extract_text(empty)


def test_corrupt_docx_raises_instead_of_indexing_error_text(tmp_path: Path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"this is not a zip archive")
    with pytest.raises(ValueError, match="DOCX extraction failed"):
        extract_text(broken)
