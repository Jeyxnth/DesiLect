"""AI4Bharat Indic-TTS (FastPitch + HiFi-GAN) for Tamil: the Plan B engine, selected with TAMIL_TTS=indic-tts.

Non-autoregressive, so it is far faster than Indic Parler-TTS on CPU, always returns the same audio for the same
text, and cannot stop mid-sentence. Runs through the coqui-tts library (installed without its dependencies, see
backend/requirements-models.txt); files from models/indic-tts-ta/ only (H2).
"""
from __future__ import annotations

import gc
import json
import logging
import shutil
import tempfile
from pathlib import Path

import numpy as np

from ..config import get_settings
from .audio import resample_fft
from .base import SAMPLE_RATE
from .parler_engine import physical_cores

log = logging.getLogger("blu.tts.indic")
logging.getLogger("TTS").setLevel(logging.WARNING)  # coqui logs every sentence and its processing time at INFO

DEFAULT_VOICE = "female"
SPEAKERS = {"female": "female", "male": "male"}  # voice id -> speaker name in fastpitch/speakers.pth


class IndicTTSEngine:
    name = "indic-tts"
    languages = ("ta",)

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "indic-tts-ta"
        self._synth = None
        self._tmp: Path | None = None

    def resolve_voice(self, voice: str) -> str:
        return voice if voice in SPEAKERS else DEFAULT_VOICE

    def _local_config(self) -> Path:
        """The released config points the speaker list at the authors' training folder; point it at ours."""
        cfg = json.loads((self.model_dir / "fastpitch" / "config.json").read_text(encoding="utf-8"))
        speakers = str((self.model_dir / "fastpitch" / "speakers.pth").resolve())
        cfg["speakers_file"] = speakers
        cfg.setdefault("model_args", {})["speakers_file"] = speakers
        self._tmp = Path(tempfile.mkdtemp(prefix="indic-tts-"))
        path = self._tmp / "config.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return path

    def load(self) -> None:
        if self._synth is not None:
            return
        fp, voc = self.model_dir / "fastpitch", self.model_dir / "hifigan"
        for p in (fp / "best_model.pth", fp / "config.json", fp / "speakers.pth", voc / "best_model.pth", voc / "config.json"):
            if not p.is_file():
                raise FileNotFoundError(f"{p} missing; run scripts/download_models.py indic-tts-ta")
        import warnings

        import torch

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            try:
                from TTS.utils.synthesizer import Synthesizer
            except ImportError as exc:
                raise ImportError("coqui-tts is not installed; see backend/requirements-models.txt") from exc

        torch.set_num_threads(physical_cores())
        self._synth = Synthesizer(
            tts_checkpoint=str(fp / "best_model.pth"),
            tts_config_path=str(self._local_config()),
            tts_speakers_file=str(fp / "speakers.pth"),
            vocoder_checkpoint=str(voc / "best_model.pth"),
            vocoder_config=str(voc / "config.json"),
            use_cuda=False,
        )
        log.info("indic-tts (ta) loaded (%d threads)", torch.get_num_threads())

    def unload(self) -> None:
        self._synth = None
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None
        gc.collect()

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        """One sentence of Tamil. speed > 1 talks faster (FastPitch's duration scale is 1 / speed)."""
        if lang not in self.languages:
            raise NotImplementedError(f"Indic-TTS engine here is Tamil only, not {lang!r}")
        self.load()
        assert self._synth is not None
        model = self._synth.tts_model
        model.length_scale = 1.0 / max(speed, 0.1)
        wav = self._synth.tts(text, speaker_name=SPEAKERS[self.resolve_voice(voice)], split_sentences=False)
        audio = np.asarray(wav, dtype=np.float32)
        return resample_fft(audio, int(self._synth.output_sample_rate), SAMPLE_RATE), SAMPLE_RATE
