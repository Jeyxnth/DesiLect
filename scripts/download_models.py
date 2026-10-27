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
    "kokoro": ("hexgrad/Kokoro-82M", "kokoro", "Apache-2.0"),
    "indictrans2": ("ai4bharat/indictrans2-en-indic-dist-200M", "indictrans2-en-indic-dist-200M", "MIT"),
    "indic-parler-tts": ("ai4bharat/indic-parler-tts", "indic-parler-tts", "Apache-2.0"),
}
# Ollama model is pulled separately: `ollama pull <OLLAMA_MODEL>` (see .env.example). TODO(step 5)


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
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("huggingface_hub is required: pip install huggingface_hub", file=sys.stderr)
            return 1
        snapshot_download(repo_id=repo, local_dir=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
