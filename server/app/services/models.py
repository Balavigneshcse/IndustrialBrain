"""Retrieval models: bge-small embeddings and a cross-encoder reranker (ONNX on CPU via fastembed).

Models are loaded once per process from MODELS_DIR with network access disabled, so the server
never downloads anything at runtime (ml/setup/03_download_models_data.sh fetches them).
"""
import math
import os
import threading

from ..core.config import get_settings

os.environ.setdefault("HF_HUB_OFFLINE", "1")

EMBEDDING_DIM = 384
_lock = threading.Lock()
_embedder = None
_reranker = None


class ModelUnavailable(RuntimeError):
    pass


def _load(kind: str):
    settings = get_settings()
    if not settings.models_path.is_dir():
        raise ModelUnavailable(f"{settings.models_path} not found; run ml/setup/03_download_models_data.sh")
    try:
        if kind == "embedder":
            from fastembed import TextEmbedding
            return TextEmbedding(settings.embedding_model, cache_dir=str(settings.models_path),
                                 threads=settings.model_threads, local_files_only=True)
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        return TextCrossEncoder(settings.reranker_model, cache_dir=str(settings.models_path),
                                threads=settings.model_threads, local_files_only=True)
    except Exception as exc:  # missing files, corrupt cache
        raise ModelUnavailable(f"could not load {kind} from {settings.models_path}: {exc}") from exc


def embedder():
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = _load("embedder")
    return _embedder


def reranker():
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                _reranker = _load("reranker")
    return _reranker


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in embedder().passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    return next(iter(embedder().query_embed(text))).tolist()


def rerank(query: str, passages: list[str]) -> list[float]:
    """Relevance probability (sigmoid of the cross-encoder logit) for each passage."""
    if not passages:
        return []
    return [1.0 / (1.0 + math.exp(-score)) for score in reranker().rerank(query, passages)]


def models_ready() -> tuple[bool, str | None]:
    try:
        embedder()
        reranker()
        return True, None
    except ModelUnavailable as exc:
        return False, str(exc)
