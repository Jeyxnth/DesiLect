"""Central configuration. Paths, env settings and the forced-offline switches (H2)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / "shared"
SCHEMA_DIR = SHARED_DIR / "schema"
SAMPLES_DIR = SHARED_DIR / "samples"

MIN_TARGET_SECONDS = 30
MAX_TARGET_SECONDS = 90
MIN_SPEED = 0.7  # narration speed accepted by the API (1.0 = the voice's normal pace)
MAX_SPEED = 1.3
# Part of the reuse-cache key for finished lessons: bump it when a change makes earlier lessons stale.
PIPELINE_VERSION = "11"
LANGUAGES = ("en", "hi", "ta")
LEVELS = ("beginner", "intermediate")

# Set (forced) by the app at runtime. Only scripts/download_models.py may go online.
OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
}


def apply_offline_env() -> None:
    """Force the offline environment flags (H2)."""
    os.environ.update(OFFLINE_ENV)


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader (no dependency). Real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _path_from_env(name: str, default: str) -> Path:
    p = Path(os.environ.get(name, default))
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    ollama_model: str
    models_dir: Path
    outputs_dir: Path
    frontend_dist: Path
    host: str
    port: int
    tamil_tts: str = "indic-tts"  # "indic-tts" (AI4Bharat Indic-TTS, default) or "parler" (Indic Parler-TTS, slow)
    tts_translit: bool = True  # speak English terms via shared/glossary.json "tts_translit" (hi, ta)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() not in ("0", "false", "no", "off", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once and make sure the process is in offline mode."""
    _load_dotenv(REPO_ROOT / ".env")
    apply_offline_env()
    return Settings(
        ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
        models_dir=_path_from_env("MODELS_DIR", "models"),
        outputs_dir=_path_from_env("OUTPUTS_DIR", "outputs"),
        frontend_dist=REPO_ROOT / "frontend" / "dist",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        tamil_tts=os.environ.get("TAMIL_TTS", "indic-tts").strip().lower(),
        tts_translit=_flag("TTS_TRANSLIT", True),
    )
