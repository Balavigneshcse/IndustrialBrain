"""Upload validation: an extension allow-list checked against the file's leading bytes."""
from pathlib import Path

ALLOWED = {
    ".pdf": "pdf", ".docx": "zip", ".xlsx": "zip", ".pptx": "zip",
    ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff", ".bmp": "bmp",
    ".txt": "text", ".csv": "text", ".md": "text", ".json": "text", ".xml": "text",
    ".html": "text", ".htm": "text", ".eml": "text",
}
SIGNATURES = {
    "pdf": (b"%PDF-",), "zip": (b"PK\x03\x04",), "png": (b"\x89PNG\r\n\x1a\n",), "jpeg": (b"\xff\xd8\xff",),
    "tiff": (b"II*\x00", b"MM\x00*"), "bmp": (b"BM",),
}


def file_type_problem(name: str, head: bytes) -> str | None:
    """None if acceptable, otherwise a message for a 415 response."""
    suffix = Path(name).suffix.lower()
    kind = ALLOWED.get(suffix)
    if kind is None:
        return f"Unsupported file type '{suffix or '(none)'}'. Allowed: {', '.join(sorted(ALLOWED))}"
    if kind == "text":
        if b"\x00" in head:
            return f"'{name}' looks like a binary file, not {suffix} text"
        return None
    if not head.startswith(SIGNATURES[kind]):
        return f"The content of '{name}' does not match its {suffix} extension"
    return None
