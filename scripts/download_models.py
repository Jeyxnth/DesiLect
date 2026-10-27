"""Download all model weights into models/. The ONLY script allowed to use the network (H2).

Run once while online, then the app runs fully offline. Licences must also be in LICENSES.md (H5).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# name -> (huggingface repo id, target dir under models/, licence)
MODELS = {
    "kokoro": ("hexgrad/Kokoro-82M", "kokoro", "Apache-2.0"),  # fetched as ONNX files, see KOKORO_FILES
    "indictrans2": ("ai4bharat/indictrans2-en-indic-dist-200M", "indictrans2-en-indic-dist-200M", "MIT"),
    "indic-parler-tts": ("ai4bharat/indic-parler-tts", "indic-parler-tts", "Apache-2.0"),
    "ollama": ("llama3.2:3b", "(ollama store)", "Llama 3.2 Community License"),  # planner LLM, `ollama pull`
}
# kokoro-onnx model files (weights Apache-2.0, kokoro-onnx runtime MIT), saved into models/kokoro/
KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]

# The planner model is pulled with the Ollama CLI into Ollama's own store (needs the ollama binary).


def download_kokoro(target: Path) -> None:
    """Fetch the two kokoro-onnx files (skips files already present)."""
    import urllib.request

    target.mkdir(parents=True, exist_ok=True)
    for fname in KOKORO_FILES:
        dest = target / fname
        if dest.is_file() and dest.stat().st_size > 0:
            print(f"  {fname}: already present")
            continue
        print(f"  downloading {fname} ...")
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(f"{KOKORO_BASE}/{fname}", tmp)
        tmp.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("models", nargs="*", help=f"subset of {', '.join(MODELS)} (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="only print what would be downloaded")
    args = ap.parse_args()

    names = args.models or list(MODELS)
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        ap.error(f"unknown model(s): {', '.join(unknown)}; choose from {', '.join(MODELS)}")

    for name in names:
        repo, subdir, licence = MODELS[name]
        target = REPO_ROOT / "models" / subdir
        print(f"{name}: {repo} ({licence}) -> {target}")
        if args.dry_run:
            continue
        os.environ["HF_HUB_OFFLINE"] = "0"  # this script is the network exception
        if name == "kokoro":
            download_kokoro(target)
            continue
        if name == "ollama":
            import shutil
            import subprocess

            if shutil.which("ollama") is None:
                print("ollama is not installed; install it from ollama.com first", file=sys.stderr)
                return 1
            model = os.environ.get("OLLAMA_MODEL", repo)
            if subprocess.run(["ollama", "pull", model]).returncode != 0:
                return 1
            continue
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("huggingface_hub is required: pip install huggingface_hub", file=sys.stderr)
            return 1
        snapshot_download(repo_id=repo, local_dir=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
