from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, File, UploadFile, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from .models import QuestionRequest, RcaRequest, ProcessPathRequest
from .extraction import extract_text, extract_entities, classify_document
from .index_store import store, chunk_pages
from .generation import generate_answer, generate_rca
from .docx_report import create_rca_docx
from .config import settings

app = FastAPI(
    title="IndusMind AI Service",
    version="1.0.0",
    description="Lightweight document intelligence, retrieval, citation, and RCA service.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


SUPPORTED_SUFFIXES = {
    ".pdf", ".txt", ".csv", ".docx",
    ".jpg", ".jpeg", ".png", ".tiff", ".bmp",
    ".xlsx", ".xls", ".pptx", ".md", ".json",
    ".xml", ".html", ".htm", ".eml", ".msg"
}


@app.get("/ai/health")
def health() -> dict:
    return {
        "status": "UP",
        "service": "ai-service",
        "vectorEngine": store.engine,
        "chunks": store.count(),
        "generationMode": "gemini" if settings.gemini_api_key else "offline-evidence",
        "ocrConfigured": bool(settings.tesseract_cmd),
    }


@app.post("/ai/documents/process")
async def process_document(
        file: UploadFile = File(...),
        document_id: str = "",
        original_name: str = "") -> dict:
    if not document_id or not original_name:
        raise HTTPException(400, "document_id and original_name are required")
    suffix = Path(original_name).suffix.lower()
    if suffix and suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, f"Unsupported document type: {suffix}")
    with NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(await file.read())
        temp_path = Path(handle.name)
    try:
        text, pages = extract_text(temp_path)
        if not text.strip():
            raise HTTPException(422, "No readable text was found. Install/configure Tesseract for scanned PDFs.")
        entities = extract_entities(text)
        doc_type = classify_document(original_name, text)
        chunks = chunk_pages(pages)
        store.add(document_id, original_name, chunks, entities, doc_type)
        return {
            "document_id": document_id,
            "document_type": doc_type,
            "asset_tags": entities["asset_tags"],
            "entities": entities,
            "chunks": len(chunks),
            "summary": f"Indexed {len(chunks)} evidence chunks and found {len(entities['asset_tags'])} asset tags.",
            "vector_engine": store.engine,
        }
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/ai/documents/process-path")
def process_document_path(request: ProcessPathRequest) -> dict:
    path = Path(request.file_path).resolve()
    suffix = Path(request.original_name).suffix.lower()
    if suffix and suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, f"Unsupported document type: {suffix}")
    if not path.is_file():
        raise HTTPException(404, "Uploaded file is not accessible to the AI service")
    text, pages = extract_text(path)
    if not text.strip():
        raise HTTPException(422, "No readable text was found. Install/configure Tesseract for scanned PDFs.")
    entities = extract_entities(text)
    doc_type = classify_document(request.original_name, text)
    chunks = chunk_pages(pages)
    store.add(request.document_id, request.original_name, chunks, entities, doc_type)
    return {
        "document_id": request.document_id,
        "document_type": doc_type,
        "asset_tags": entities["asset_tags"],
        "entities": entities,
        "chunks": len(chunks),
        "summary": f"Indexed {len(chunks)} evidence chunks and found {len(entities['asset_tags'])} asset tags.",
        "vector_engine": store.engine,
    }


@app.post("/ai/answer")
def answer(request: QuestionRequest) -> dict:
    evidence = store.search(request.question, request.asset_tag, 3)
    answer_text, mode = generate_answer(request.question, evidence, getattr(request, "desired_format", "quick_answer"))
    confidence = 0.0 if not evidence else min(
        0.94, 0.55 + len(evidence) * 0.035 + max(item["score"] for item in evidence) * 0.22
    )
    citations = [
        {
            "source": item["metadata"]["source"],
            "page": item["metadata"]["page"],
            "documentType": item["metadata"].get("document_type", ""),
            "excerpt": item["text"][:360],
            "relevance": round(min(0.97, 0.5 + item["score"] * 0.45), 2),
        }
        for item in evidence
    ]
    return {
        "answer": answer_text,
        "mode": mode,
        "confidence": round(confidence, 2),
        "citations": citations,
        "assetTag": request.asset_tag.upper() if request.asset_tag else "",
    }


@app.get("/ai/assets/{tag}")
def asset(tag: str) -> dict:
    evidence = store.asset(tag)
    if not evidence:
        raise HTTPException(404, f"No indexed evidence found for {tag.upper()}")
    sources, failures, actions, dates, measurements = set(), set(), set(), set(), set()
    events = []
    for item in evidence:
        meta = item["metadata"]
        sources.add(meta["source"])
        failures.update(filter(None, meta.get("failures", "").split(",")))
        actions.update(filter(None, meta.get("actions", "").split(",")))
        dates.update(filter(None, meta.get("dates", "").split(",")))
        measurements.update(filter(None, meta.get("measurements", "").split(",")))
        if meta.get("dates"):
            events.append({
                "date": meta["dates"].split(",")[0],
                "source": meta["source"],
                "summary": item["text"][:220],
            })
    return {
        "tag": tag.upper(),
        "sources": sorted(sources),
        "failures": sorted(failures),
        "maintenanceActions": sorted(actions),
        "dates": sorted(dates),
        "measurements": sorted(measurements),
        "timeline": events[:12],
        "evidenceChunks": len(evidence),
    }


@app.post("/ai/rca")
def rca(request: RcaRequest) -> dict:
    evidence = store.asset(request.asset_tag)
    if not evidence:
        raise HTTPException(404, f"No indexed evidence found for {request.asset_tag.upper()}")
    result = generate_rca(request.asset_tag, evidence)
    result["citations"] = [
        {"source": item["metadata"]["source"], "page": item["metadata"]["page"], "excerpt": item["text"][:280]}
        for item in evidence[:5]
    ]
    return result


@app.get("/ai/rca/export-docx/{tag}")
def export_rca_docx(tag: str):
    evidence = store.asset(tag)
    if not evidence:
        raise HTTPException(404, f"No indexed evidence found for {tag.upper()}")
    result = generate_rca(tag, evidence)
    result["citations"] = [
        {"source": item["metadata"]["source"], "page": item["metadata"]["page"], "excerpt": item["text"][:280]}
        for item in evidence[:5]
    ]
    docx_bytes = create_rca_docx(result)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="RCA_{tag.upper()}.docx"'}
    )
