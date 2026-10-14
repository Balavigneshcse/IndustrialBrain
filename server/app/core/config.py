"""Application settings, read from environment variables and the repository-root .env file."""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
INSECURE_DEV_SECRET = "dev-only-insecure-secret-do-not-use-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    indusmind_env: Literal["development", "test", "production"] = "development"
    secret_key: SecretStr = SecretStr(INSECURE_DEV_SECRET)

    # Either a full SQLAlchemy URL, or the POSTGRES_* parts (as used by docker-compose).
    database_url: str | None = None
    postgres_user: str = "indusmind"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "indusmind"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433

    upload_dir: Path = Path("data/uploads")
    max_upload_mb: int = 50
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    tesseract_cmd: str = ""

    # Auth
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    min_password_length: int = 8

    # Per-minute rate limits (shared through Redis when REDIS_URL is set, otherwise per process)
    login_rate_per_minute: int = 5
    chat_rate_per_minute: int = 20
    upload_rate_per_minute: int = 30

    # Background jobs. Without REDIS_URL, uploads are processed inline in the API process.
    redis_url: str | None = None
    celery_eager: bool | None = None  # None: eager exactly when REDIS_URL is not set

    # Retrieval models (ONNX on CPU via fastembed, loaded from MODELS_DIR without network access)
    models_dir: Path = Path("data/models/fastembed")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    model_threads: int | None = None

    # Retrieval tuning
    retrieval_candidates: int = 30   # per retriever (vector and keyword) before fusion
    rerank_candidates: int = 20      # fused candidates passed to the cross-encoder
    # Below this reranker probability the answer is "insufficient evidence". Kept low on purpose: on the
    # benchmark, correct passages for differently-worded questions score 0.007-0.1, while unrelated
    # questions score ~0.000. Deciding that a specific fact is absent from relevant evidence (e.g.
    # "motor current") is left to the language model in Phase 3. See eval/README.md.
    min_evidence_score: float = 0.005

    # Answer generation (Ollama on the host GPU). If Ollama is unreachable, answers fall back to the
    # extractive evidence summary and say so. Keep num_ctx/num_gpu identical in every request: a
    # different value makes Ollama reload the model.
    llm_enabled: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    llm_num_ctx: int = 4096
    llm_num_gpu: int = 99            # all layers on the GPU (automatic placement left a third on the CPU)
    llm_keep_alive: int = -1         # seconds the model stays loaded after a call; negative = always
    llm_temperature: float = 0.1
    llm_seed: int | None = 42        # fixed: the same question over the same evidence gets the same answer
    llm_max_answer_tokens: int = 600
    llm_context_chunks: int = 6      # sources given to the model (and returned as citations)
    llm_concurrency: int = 2         # match OLLAMA_NUM_PARALLEL
    llm_max_queue: int = 16          # questions waiting for a slot before the API answers 429
    llm_timeout_seconds: float = 120.0
    llm_breaker_failures: int = 3    # consecutive failures that open the circuit breaker
    llm_breaker_cooldown_seconds: float = 30.0

    log_json: bool = True

    @property
    def jobs_eager(self) -> bool:
        return self.celery_eager if self.celery_eager is not None else not self.redis_url

    @property
    def models_path(self) -> Path:
        path = self.models_dir if self.models_dir.is_absolute() else REPO_ROOT / self.models_dir
        return path.resolve()

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        password = quote(self.postgres_password.get_secret_value(), safe="")
        return (f"postgresql+asyncpg://{self.postgres_user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    @property
    def upload_path(self) -> Path:
        path = self.upload_dir if self.upload_dir.is_absolute() else REPO_ROOT / self.upload_dir
        return path.resolve()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _production_needs_real_secrets(self) -> "Settings":
        if self.indusmind_env == "production":
            secret = self.secret_key.get_secret_value()
            if secret == INSECURE_DEV_SECRET or len(secret) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production")
            if not self.database_url and not self.postgres_password.get_secret_value():
                raise ValueError("DATABASE_URL or POSTGRES_PASSWORD must be set in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production (serve over HTTPS)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
