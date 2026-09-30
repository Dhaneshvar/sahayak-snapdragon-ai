"""Runtime configuration, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # OpenAI-compatible local endpoint. Empty = auto-discover Foundry Local.
    llm_base_url: str = field(default_factory=lambda: _env("SAHAYAK_LLM_BASE_URL", ""))
    # Model alias or id; matched against the endpoint's /v1/models list.
    llm_model: str = field(default_factory=lambda: _env("SAHAYAK_LLM_MODEL", "phi-3.5-mini"))
    # Privacy guard: refuse non-loopback endpoints unless explicitly allowed.
    allow_remote: bool = field(default_factory=lambda: _flag("SAHAYAK_ALLOW_REMOTE"))
    llm_timeout_s: int = field(default_factory=lambda: int(_env("SAHAYAK_LLM_TIMEOUT", "180")))
    max_document_chars: int = field(default_factory=lambda: int(_env("SAHAYAK_MAX_DOC_CHARS", "12000")))
    max_file_mb: int = field(default_factory=lambda: int(_env("SAHAYAK_MAX_FILE_MB", "20")))
