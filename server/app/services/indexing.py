"""Chunking and embeddings.

The embedding is still the hashed bag-of-words vector from the original service (384 dims, so it
fits the same pgvector column). Phase 2 swaps it for bge-small-en-v1.5, also 384 dims.
"""
import hashlib
import math
import re
from collections import Counter

VECTOR_SIZE = 384
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]{2,}")


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
