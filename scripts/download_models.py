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
    "indictrans2": ("ai4bharat/indictrans2-en-indic-dist-200M", "indictrans2", "MIT"),
    "indic-parler-tts": ("ai4bharat/indic-parler-tts", "indic-parler-tts", "Apache-2.0"),
    "ollama": ("llama3.2:3b", "(ollama store)", "Llama 3.2 Community License"),  # planner LLM, `ollama pull`
    # Plan B Tamil TTS (FastPitch + HiFi-GAN), a GitHub release zip, see INDIC_TTS_URL
    "indic-tts-ta": ("AI4Bharat/Indic-TTS v1-checkpoints-release ta.zip", "indic-tts-ta", "MIT"),
}
INDIC_TTS_URL = "https://github.com/AI4Bharat/Indic-TTS/releases/download/v1-checkpoints-release/{lang}.zip"
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


def download_indic_tts(target: Path, lang: str) -> None:
    """Fetch and unpack one language of AI4Bharat Indic-TTS (about 1.5 GB zip; skipped if already unpacked)."""
    import shutil
    import urllib.request
    import zipfile

    if any(target.rglob("best_model.pth")):
        print("  already present")
        return
    target.mkdir(parents=True, exist_ok=True)
    archive = target / f"{lang}.zip"
    if not archive.is_file():
        print(f"  downloading {lang}.zip (about 1.5 GB) ...")
        tmp = archive.with_suffix(".zip.part")
        urllib.request.urlretrieve(INDIC_TTS_URL.format(lang=lang), tmp)
        tmp.replace(archive)
    print("  unpacking ...")
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():  # refuse paths that would escape the target folder
            if Path(member).is_absolute() or ".." in Path(member).parts:
                raise ValueError(f"unsafe path in {archive.name}: {member}")
        z.extractall(target)
    archive.unlink()
    nested = target / lang  # the zip holds <lang>/...; flatten it to models/indic-tts-<lang>/
    if nested.is_dir():
        for item in nested.iterdir():
            shutil.move(str(item), target / item.name)
        nested.rmdir()


def download_parler_description_tokenizer(target: Path) -> None:
    """Indic Parler-TTS encodes its speaker description with its text encoder's tokenizer (tokenizer files
    only, a few MB). Without a local copy the model would try to fetch it from the Hub at runtime (H2)."""
    import json

    from huggingface_hub import snapshot_download

    origin = json.loads((target / "config.json").read_text(encoding="utf-8"))["text_encoder"]["_name_or_path"]
    dest = target / "description_tokenizer"
    print(f"  description tokenizer: {origin} -> {dest}")
    snapshot_download(
        repo_id=origin,
        local_dir=dest,
        allow_patterns=["tokenizer*", "spiece.model", "special_tokens_map.json", "added_tokens.json", "LICENSE*"],
    )


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
        if name == "indic-tts-ta":
            download_indic_tts(target, "ta")
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
            from huggingface_hub.errors import GatedRepoError
        except ImportError:
            print("huggingface_hub is required: pip install huggingface_hub", file=sys.stderr)
            return 1
        try:
            snapshot_download(repo_id=repo, local_dir=target)
            if name == "indic-parler-tts":
                download_parler_description_tokenizer(target)
        except GatedRepoError:
            print(
                f"\n{repo} is gated on Hugging Face. Once per machine:\n"
                f"  1. Sign in at huggingface.co and open https://huggingface.co/{repo}\n"
                "     and accept the access conditions (approval is automatic).\n"
                "  2. Create a read token: https://huggingface.co/settings/tokens\n"
                "  3. Run: .venv/Scripts/hf auth login   (paste the token; it is stored in your user profile, not in this repo)\n"
                f"  4. Run this script again: python scripts/download_models.py {name}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
