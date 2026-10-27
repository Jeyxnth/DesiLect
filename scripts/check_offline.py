"""Offline readiness check (H2): everything the app needs is on disk and nothing reaches the internet.

    python scripts/check_offline.py          # files, tools, Ollama model, source + built assets scan
    python scripts/check_offline.py --deep   # also run IndicTrans2, Kokoro, Indic-TTS and a capture browser once

Runs with HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 and with outbound sockets blocked inside this
process (only 127.0.0.1 / localhost / ::1 may be reached), so a hidden download fails here, not at the demo.
Exits non-zero with the list of what is missing.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

for _k, _v in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
               "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}.items():
    os.environ[_k] = _v

# ---------------------------------------------------------------- socket guard

class OutboundBlocked(OSError):
    """A connection to a non-loopback address was attempted while offline."""


BLOCKED: list[str] = []  # every refused destination, reported at the end
_create_connection = socket.create_connection
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host.lower() in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _check(address: object) -> None:
    if isinstance(address, tuple) and address and not is_loopback(address[0]):
        BLOCKED.append(f"{address[0]}:{address[1] if len(address) > 1 else '?'}")
        raise OutboundBlocked(f"offline check: outbound connection to {address[0]} blocked")


def _guarded_create_connection(address, *args, **kwargs):  # type: ignore[no-untyped-def]
    _check(address)
    return _create_connection(address, *args, **kwargs)


def _guarded_connect(self, address):  # type: ignore[no-untyped-def]
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _check(address)
    return _connect(self, address)


def _guarded_connect_ex(self, address):  # type: ignore[no-untyped-def]
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _check(address)
    return _connect_ex(self, address)


def block_outbound() -> None:
    """Allow only loopback connections in this process (other processes are not affected)."""
    socket.create_connection = _guarded_create_connection  # type: ignore[assignment]
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]


# ---------------------------------------------------------------- reporting

MISSING: list[str] = []
WARNINGS: list[str] = []


def need(label: str, ok: bool, fix: str = "") -> bool:
    print(f"  [{'ok' if ok else 'MISSING'}] {label}")
    if not ok:
        MISSING.append(f"{label}" + (f"  ->  {fix}" if fix else ""))
    return ok


def optional(label: str, ok: bool, why: str) -> None:
    print(f"  [{'ok' if ok else 'warn'}] {label}")
    if not ok:
        WARNINGS.append(f"{label}: {why}")


def files_in(d: Path, names: list[str]) -> list[str]:
    return [n for n in names if not (d / n).is_file() or (d / n).stat().st_size == 0]


# ---------------------------------------------------------------- checks

def check_guard() -> None:
    print("socket guard")
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2)
        need("outbound connections are blocked", False, "the socket guard did not engage")
    except OutboundBlocked:
        need("outbound connections are blocked (loopback only)", True)
    except OSError:
        need("outbound connections are blocked", False, "unexpected network error before the guard")
    BLOCKED.clear()  # that one was ours


def check_models(models: Path) -> None:
    from app.config import get_settings

    tamil = get_settings().tamil_tts
    print(f"models ({models})")
    fix = "run once while online: python scripts/download_models.py "
    k = models / "kokoro"
    need("Kokoro (kokoro-v1.0.onnx, voices-v1.0.bin)", not files_in(k, ["kokoro-v1.0.onnx", "voices-v1.0.bin"]), fix + "kokoro")
    it = models / "indictrans2"
    miss = files_in(it, ["config.json", "dict.SRC.json", "dict.TGT.json", "model.SRC", "model.TGT", "tokenizer_config.json",
                         "modeling_indictrans.py", "tokenization_indictrans.py", "configuration_indictrans.py"])
    weights = (it / "model.safetensors").is_file() or (it / "pytorch_model.bin").is_file()
    need("IndicTrans2 en->indic" + (f" (missing {', '.join(miss)})" if miss else ""), not miss and weights, fix + "indictrans2")
    ttd = models / "indic-tts-ta"
    miss = files_in(ttd, ["fastpitch/best_model.pth", "fastpitch/config.json", "fastpitch/speakers.pth",
                          "hifigan/best_model.pth", "hifigan/config.json"])
    tts_ok = not miss
    label = "Indic-TTS Tamil (FastPitch + HiFi-GAN)" + (f" (missing {', '.join(miss)})" if miss else "")
    if tamil == "indic-tts":
        need(label, tts_ok, fix + "indic-tts-ta")
    else:
        optional(label, tts_ok, "only used when TAMIL_TTS=indic-tts")
    pd = models / "indic-parler-tts"
    miss = files_in(pd, ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                         "description_tokenizer/tokenizer.json", "description_tokenizer/spiece.model"])
    label = "Indic Parler-TTS" + (f" (missing {', '.join(miss)})" if miss else "")
    if tamil == "parler":
        need(label, not miss, fix + "indic-parler-tts")
    else:
        optional(label, not miss, f"opt-in Tamil voice (TAMIL_TTS=parler); this machine uses TAMIL_TTS={tamil}")


def ollama_models_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def check_ollama() -> None:
    import httpx

    from app.config import get_settings

    s = get_settings()
    name, _, tag = s.ollama_model.partition(":")
    print(f"Ollama ({s.ollama_model})")
    manifest = ollama_models_dir() / "manifests" / "registry.ollama.ai" / "library" / name / (tag or "latest")
    need(f"model {s.ollama_model} on disk ({manifest.parent.parent.parent.parent.parent})", manifest.is_file(),
         f"run once while online: ollama pull {s.ollama_model}")
    if not is_loopback(httpx.URL(s.ollama_url).host):
        need(f"OLLAMA_URL is local ({s.ollama_url})", False, "point OLLAMA_URL at 127.0.0.1 (H1)")
        return
    try:
        r = httpx.get(f"{s.ollama_url}/api/tags", timeout=2)
        names = [m["name"] for m in r.json().get("models", [])]
        want = s.ollama_model if ":" in s.ollama_model else s.ollama_model + ":latest"
        need(f"Ollama server answers and lists {want}", want in names, f"ollama pull {s.ollama_model}")
    except (httpx.HTTPError, ValueError, KeyError):
        optional("Ollama server running", False, "start Ollama before the demo; without it lessons use the built-in samples")


def check_assets() -> None:
    print("fonts, samples, cached narration")
    fonts = REPO_ROOT / "frontend" / "public" / "fonts"
    names = ["NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoSansMono-Regular.ttf", "NotoSansDevanagari-Regular.woff2",
             "NotoSansDevanagari-Bold.woff2", "NotoSansTamil-Regular.woff2", "NotoSansTamil-Bold.woff2"]
    miss = files_in(fonts, names)
    need("Noto fonts in frontend/public/fonts" + (f" (missing {', '.join(miss)})" if miss else ""), not miss,
         "see frontend/public/fonts/README.md")
    samples = REPO_ROOT / "shared" / "samples"
    from app.planner.fallback import SAMPLES

    miss = [f"{s.name}.{lang}.json" for s in SAMPLES for lang in ("en", "hi", "ta") if not (samples / f"{s.name}.{lang}.json").is_file()]
    need("fallback samples in en/hi/ta" + (f" (missing {', '.join(miss)})" if miss else ""), not miss)
    cache = REPO_ROOT / "shared" / "tts_cache"
    import json

    for lang in ("en", "hi", "ta"):
        man = cache / "manifest" / f"{lang}.json"
        keys = json.loads(man.read_text(encoding="utf-8")) if man.is_file() else {}
        missing = [k for k in keys if not (cache / f"{k}.flac").is_file()]
        need(f"bundled sample narration ({lang}): {len(keys)} sentences", bool(keys) and not missing,
             "run: python scripts/pregen_audio.py " + lang)


def check_tools() -> None:
    print("tools")
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    need("ffmpeg and ffprobe on PATH", bool(ff and fp), "install FFmpeg (winget install Gyan.FFmpeg)")
    if ff:
        out = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
        need("ffmpeg has libx264 and aac", "libx264" in out and " aac " in out)
    try:
        import playwright  # noqa: F401
        need("playwright (Python) installed", True)
    except ImportError:
        need("playwright (Python) installed", False, "pip install playwright")
    dist = REPO_ROOT / "frontend" / "dist" / "index.html"
    need("frontend built (frontend/dist)", dist.is_file(), "cd frontend && npm run build")


def check_browser() -> None:
    """Launch the capture browser the way the exporter does (bundled Chromium, else Chrome, else Edge)."""
    print("capture browser")
    try:
        from playwright.sync_api import sync_playwright

        from app.export.capture import _launch

        with sync_playwright() as p:
            browser = _launch(p)
            version = browser.version
            browser.close()
        need(f"Chromium launches headless ({version})", True)
    except Exception as exc:  # noqa: BLE001
        need("Chromium launches headless", False, f"python -m playwright install chromium (online once): {str(exc)[:120]}")


# A built bundle may name these without fetching them: XML namespace URIs and React's error-decoder text.
ALLOWED_URL = re.compile(r"^https?://(www\.w3\.org/|reactjs\.org/docs/error-decoder)")
URL_RE = re.compile(r"https?://[^\s\"'`)>\\]+")
LOCAL_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:[\w{}]+)?(/|$)")
BAD_WORDS = re.compile(r"fonts\.googleapis|fonts\.gstatic|cdn\.|unpkg|jsdelivr|googletagmanager|sentry|analytics", re.I)
SOURCE_SCAN = [REPO_ROOT / "frontend" / "src", REPO_ROOT / "frontend" / "index.html", REPO_ROOT / "backend" / "app"]
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json"}


def scan_urls(paths: list[Path], allow: re.Pattern[str] | None = None) -> list[str]:
    problems: list[str] = []
    files = []
    for base in paths:
        if base.is_file():
            files.append(base)
        elif base.is_dir():
            files += [p for p in base.rglob("*") if p.is_file() and p.suffix in EXTENSIONS
                      and "node_modules" not in p.parts and "__pycache__" not in p.parts]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO_ROOT)
        for url in sorted(set(URL_RE.findall(text))):
            if not LOCAL_RE.match(url) and not (allow and allow.match(url)):
                problems.append(f"{rel}: external URL {url}")
        for word in sorted(set(m.group(0) for m in BAD_WORDS.finditer(text))):
            problems.append(f"{rel}: suspicious reference {word!r}")
    return problems


def check_urls() -> None:
    print("external URLs")
    src = scan_urls(SOURCE_SCAN)
    for p in src:
        print("   ", p)
    need("no external URLs in frontend/src, index.html, backend/app", not src)
    dist = REPO_ROOT / "frontend" / "dist"
    built = scan_urls([dist], ALLOWED_URL) if dist.is_dir() else []
    for p in built:
        print("   ", p)
    need("no external URLs in the built frontend (frontend/dist)", dist.is_dir() and not built, "remove the URL and rebuild")


# ---------------------------------------------------------------- deep: run each model once

def deep() -> None:
    print("deep: each model runs once with the network blocked")
    from app.config import get_settings

    try:
        from app.translate import indictrans

        out = indictrans.translate_texts(["The loop runs five times."], "hi")
        indictrans.unload()
        need(f"IndicTrans2 translates offline ({out[0][:40]})", bool(out and out[0].strip()))
    except Exception as exc:  # noqa: BLE001
        need("IndicTrans2 translates offline", False, f"{type(exc).__name__}: {str(exc)[:160]}")
    from app.tts.registry import get_engine, release_all

    tests = [("en", "The loop runs five times."), ("ta", "இது ஒரு சோதனை.")]
    for lang, text in tests:
        try:
            engine, voice = get_engine(lang)
            samples, sr = engine.synth(text, lang, voice, 1.0)
            need(f"{engine.name} speaks {lang} offline ({len(samples) / sr:.1f} s)", len(samples) / sr > 0.3)
        except Exception as exc:  # noqa: BLE001
            need(f"TTS speaks {lang} offline", False, f"{type(exc).__name__}: {str(exc)[:160]}")
        finally:
            release_all()
    if get_settings().tamil_tts != "parler":
        print("  (Parler not loaded: TAMIL_TTS is not parler)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deep", action="store_true", help="also run IndicTrans2 and the TTS engines once (about a minute)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    block_outbound()

    from app.config import get_settings

    check_guard()
    check_models(get_settings().models_dir)
    check_ollama()
    check_assets()
    check_tools()
    check_browser()
    check_urls()
    if args.deep:
        deep()

    if BLOCKED:
        need("nothing tried to reach the internet", False, "blocked: " + ", ".join(sorted(set(BLOCKED))))
    print()
    for w in WARNINGS:
        print("warning:", w)
    if MISSING:
        print(f"offline-check: FAIL, {len(MISSING)} missing:")
        for m in MISSING:
            print("  -", m)
        return 1
    print("offline-check: OK (everything on disk; no outbound connections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
