"""Preflight: is this machine ready to run and test Blu Visual Teacher? (make doctor)

Standard library only, so it runs on a fresh laptop before `make setup`.
Checks marked `since=N` become hard requirements at step N; earlier they are only warnings.
Exit code 1 if any required check fails.

    python scripts/doctor.py            # fast checks
    python scripts/doctor.py --smoke    # also synthesise one sentence with Kokoro
"""
from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CURRENT_STEP = 5  # bump this each step so newly needed dependencies become hard requirements

REPO = Path(__file__).resolve().parents[1]
VENV_PY = REPO / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    fix: str = ""


results: list[Result] = []


def report(name: str, ok: bool, detail: str = "", fix: str = "", since: int = 1) -> bool:
    status = OK if ok else (FAIL if since <= CURRENT_STEP else WARN)
    if not ok and since > CURRENT_STEP:
        detail = f"{detail} (needed from step {since})".strip()
    results.append(Result(name, status, detail, "" if ok else fix))
    return ok


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def venv_run(code: str, timeout: int = 120) -> tuple[int, str]:
    return run([str(VENV_PY), "-I", "-c", code], timeout)


def ram_gb() -> float | None:
    if os.name == "nt":
        class MEM(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                        ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
        m = MEM()
        m.l = ctypes.sizeof(MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))  # type: ignore[attr-defined]
        return m.total / 2**30
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):
        return None


def check_machine() -> None:
    gb = ram_gb()
    report("RAM >= 8 GB", gb is None or gb >= 7.5, f"{gb:.1f} GB" if gb else "unknown", "Needs an 8-16 GB machine (rule H3).")
    free = shutil.disk_usage(REPO).free / 2**30
    report("Free disk >= 5 GB", free >= 5, f"{free:.1f} GB free", "Models need several GB; free some disk space.")
    report("CPU only is fine", True, f"{os.cpu_count()} logical cores, {platform.system()} {platform.machine()}")


def check_python() -> None:
    v = sys.version_info
    report("Python >= 3.10 (target 3.11)", v >= (3, 10), platform.python_version(),
           "Install Python 3.11 from python.org (or `winget install Python.Python.3.11`).")
    if v >= (3, 10) and v[:2] != (3, 11):
        results.append(Result("Python is exactly 3.11", WARN, f"found {v[0]}.{v[1]}; project targets 3.11 (rule G9)"))
    has_venv = VENV_PY.is_file()
    report("Virtualenv .venv exists", has_venv, str(VENV_PY), "Run: make setup   (or: python -m venv .venv)")
    if not has_venv:
        return
    mods = {"fastapi": 1, "pydantic": 1, "jsonschema": 1, "uvicorn": 1, "numpy": 2, "soundfile": 2,
            "onnxruntime": 2, "kokoro_onnx": 2, "espeakng_loader": 2, "httpx": 1, "pytest": 1, "playwright": 4}
    for mod, since in mods.items():
        code, out = venv_run(f"import {mod}")
        report(f"Python package: {mod}", code == 0, "" if code == 0 else out.splitlines()[-1][:80] if out else "",
               "Run: .venv/Scripts/python -m pip install -r backend/requirements.txt" + (
                   "  and  pip install playwright" if mod == "playwright" else ""), since)


def check_node() -> None:
    node = shutil.which("node")
    if not report("Node installed", node is not None, "", "Install Node 20 LTS (`winget install OpenJS.NodeJS.LTS`)."):
        return
    code, out = run(["node", "--version"])
    major = int(out.lstrip("v").split(".")[0]) if code == 0 and out[:1] == "v" else 0
    report("Node >= 20", major >= 20, out, "Install Node 20 LTS or newer.")
    report("npm installed", shutil.which("npm") is not None, "", "npm comes with Node.")
    report("frontend/node_modules present", (REPO / "frontend" / "node_modules" / "react").is_dir(), "",
           "Run: cd frontend && npm install")


def check_ffmpeg() -> None:
    ff = shutil.which("ffmpeg")
    if not report("ffmpeg on PATH", ff is not None, "", "Install FFmpeg (`winget install Gyan.FFmpeg`) and reopen the terminal.", since=4):
        return
    code, out = run(["ffmpeg", "-hide_banner", "-encoders"])
    report("ffmpeg has libx264 + aac", code == 0 and "libx264" in out and " aac " in out + " ", "",
           "Install a full FFmpeg build with libx264 (the Gyan.FFmpeg build has it).", since=4)


def check_browser() -> None:
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or
                 (Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt" else Path.home() / ".cache/ms-playwright"))
    bundled = cache.is_dir() and any(cache.glob("chromium*"))
    system = any(Path(p).is_file() for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    report("Chromium for Playwright (bundled or Chrome/Edge)", bundled or system,
           "bundled" if bundled else "system browser" if system else "",
           "Run: .venv/Scripts/python -m playwright install chromium   (needs network once)", since=4)


def check_models() -> None:
    k = REPO / "models" / "kokoro"
    onnx, voices = k / "kokoro-v1.0.onnx", k / "voices-v1.0.bin"
    fix = "Run once while online: python scripts/download_models.py kokoro"
    report("Kokoro model file", onnx.is_file() and onnx.stat().st_size > 300_000_000,
           f"{onnx.stat().st_size / 1e6:.0f} MB" if onnx.is_file() else "missing", fix)
    report("Kokoro voices file", voices.is_file() and voices.stat().st_size > 20_000_000,
           f"{voices.stat().st_size / 1e6:.0f} MB" if voices.is_file() else "missing", fix)
    if voices.is_file() and VENV_PY.is_file():
        code, out = venv_run(f"import numpy as n; f=n.load(r'{voices}',allow_pickle=False).files; "
                             "print(int('hf_alpha' in f or 'hm_omega' in f))")
        report("Voices hf_alpha / hm_omega present", code == 0 and out.strip().endswith("1"), "",
               "Re-download: delete models/kokoro/voices-v1.0.bin and run scripts/download_models.py kokoro")
    for label, d, since in (("IndicTrans2 model", "indictrans2-en-indic-dist-200M", 8),
                            ("Indic Parler-TTS model", "indic-parler-tts", 9)):
        p = REPO / "models" / d
        report(label, p.is_dir() and any(p.iterdir()), "" if p.is_dir() else "missing",
               "Run once while online: python scripts/download_models.py " + ("indictrans2" if since == 8 else "indic-parler-tts"), since)


def check_ollama() -> None:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=1.5) as r:
            body = r.read().decode("utf-8", "replace")
        up = True
    except OSError:
        up, body = False, ""
    if report("Ollama running on localhost", up, url, "Install Ollama and start it (`ollama serve`).", since=5):
        report(f"Ollama model {model} pulled", model in body, "", f"Run once while online: ollama pull {model}", since=5)


def check_fonts() -> None:
    fonts = REPO / "frontend" / "public" / "fonts"
    need = ["NotoSans-Regular.ttf", "NotoSansDevanagari-Regular.ttf", "NotoSansTamil-Regular.ttf", "NotoSansMono-Regular.ttf"]
    missing = [f for f in need if not (fonts / f).is_file()]
    report("Noto fonts in frontend/public/fonts", not missing, ", ".join(missing),
           "Add the files listed in frontend/public/fonts/README.md", since=10)


def smoke() -> None:
    code = ("import sys; sys.path.insert(0,'backend'); "
            "from app.tts.kokoro_engine import KokoroEngine; import time; e=KokoroEngine(); t=time.time(); "
            "a,sr=e.synth('Hello, this is a test.','en','hf_alpha'); "
            "print(f'{len(a)/sr:.2f}s audio in {time.time()-t:.2f}s'); assert len(a)/sr > 0.5")
    c, out = run([str(VENV_PY), "-c", code], timeout=300)
    report("Smoke test: Kokoro speaks", c == 0, out.splitlines()[-1] if out else "",
           "See the error above; usually missing model files or onnxruntime.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="also synthesise one sentence (needs models, ~10 s)")
    args = ap.parse_args()

    for check in (check_machine, check_python, check_node, check_ffmpeg, check_browser, check_models, check_ollama, check_fonts):
        check()
    if args.smoke and VENV_PY.is_file():
        smoke()

    width = max(len(r.name) for r in results)
    for r in results:
        print(f"[{r.status}] {r.name.ljust(width)}  {r.detail}")
        if r.fix:
            print(f"       -> {r.fix}")
    failed = [r for r in results if r.status == FAIL]
    warned = [r for r in results if r.status == WARN]
    print(f"\ndoctor (step {CURRENT_STEP}): {len(results) - len(failed) - len(warned)} ok, {len(warned)} warnings, {len(failed)} failed")
    if failed:
        print("Fix the FAIL items above, then run again.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
