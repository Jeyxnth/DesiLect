"""Indic Parler-TTS (ai4bharat/indic-parler-tts) for Tamil. CPU, float32, local files only (H2, H3)."""
from __future__ import annotations

import gc
import logging
import os

import numpy as np

from ..config import get_settings
from .audio import resample_fft
from .base import SAMPLE_RATE

log = logging.getLogger("blu.tts.parler")

# parler-tts warns on every load (each sub-model's whole config) and on the first generate. All three are expected
# here: no flash-attention on CPU, the shared configs are how the checkpoint is built, and with one unpadded sentence
# per call the decoder mask it creates (all ones) is the right one. Other parler-tts warnings still show.
_EXPECTED_NOTICES = (
    "is overwritten by shared",
    "Flash attention 2 is not installed",
    "`prompt_attention_mask` is specified but `attention_mask` is not",
)


class _DropExpectedNotices(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(notice in message for notice in _EXPECTED_NOTICES)


logging.getLogger("parler_tts.modeling_parler_tts").addFilter(_DropExpectedNotices())

SEED = 0  # reset before every sentence, so a sentence sounds the same whatever was spoken before it
DEFAULT_VOICE = "jaya"
# voice id -> speaker name known to Indic Parler-TTS. The model card lists two Tamil speakers, Jaya (recommended)
# and Kavitha, both female; there is no named male Tamil speaker.
SPEAKERS = {"jaya": "Jaya", "kavitha": "Kavitha"}
_DESCRIPTION = (
    "{speaker}'s voice is clear, warm and expressive, speaking {pace} with very clear audio, "
    "a very close recording and no background noise."
)


def physical_cores() -> int:
    """Physical CPU cores (torch is fastest with one thread per core, not per hyper-thread)."""
    try:
        import psutil

        n = psutil.cpu_count(logical=False)
        if n:
            return int(n)
    except ImportError:
        pass
    return max(1, (os.cpu_count() or 2) // 2)  # assume 2-way SMT when psutil is missing


def pace_phrase(speed: float) -> str:
    """Parler has no speed knob; the pace is part of the (fixed per speed) description."""
    if speed < 0.9:
        return "slowly"
    if speed > 1.1:
        return "a little fast"
    return "at a moderate pace"


class ParlerEngine:
    name = "parler"
    languages = ("ta",)

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "indic-parler-tts"
        self._model = None
        self._prompt_tok = None
        self._desc_tok = None

    def resolve_voice(self, voice: str) -> str:
        return voice if voice in SPEAKERS else DEFAULT_VOICE

    def description(self, voice: str, speed: float = 1.0) -> str:
        """The fixed speaker description for a voice and speed (same string -> same voice)."""
        return _DESCRIPTION.format(speaker=SPEAKERS[self.resolve_voice(voice)], pace=pace_phrase(speed))

    def _description_tokenizer_source(self, config) -> str:
        local = self.model_dir / "description_tokenizer"  # fetched by scripts/download_models.py
        if local.is_dir():
            return str(local)
        origin = str(getattr(config.text_encoder, "_name_or_path", ""))
        if origin and os.path.isdir(origin):
            return origin
        raise FileNotFoundError(
            f"{local} missing (the description tokenizer of {origin or 'the text encoder'}); "
            "run scripts/download_models.py indic-parler-tts"
        )

    def load(self) -> None:
        if self._model is not None:
            return
        if not (self.model_dir / "config.json").is_file():
            raise FileNotFoundError(f"{self.model_dir} missing; run scripts/download_models.py indic-parler-tts")
        import warnings

        import torch

        with warnings.catch_warnings():  # deprecation notices from its dependencies, not actionable here
            warnings.simplefilter("ignore", FutureWarning)
            from transformers import AutoTokenizer

            try:
                from parler_tts import ParlerTTSForConditionalGeneration
            except ImportError as exc:
                raise ImportError("parler-tts is not installed; see backend/requirements-models.txt") from exc

        torch.set_num_threads(physical_cores())
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            str(self.model_dir), local_files_only=True, torch_dtype=torch.float32
        )
        self._model = model.to("cpu").eval()
        self._prompt_tok = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        self._desc_tok = AutoTokenizer.from_pretrained(
            self._description_tokenizer_source(model.config), local_files_only=True
        )
        log.info("indic-parler-tts loaded (%d threads)", torch.get_num_threads())

    def unload(self) -> None:
        self._model = self._prompt_tok = self._desc_tok = None
        gc.collect()

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        """One sentence of Tamil. Seeded, so repeated calls give identical audio."""
        if lang not in self.languages:
            raise NotImplementedError(f"Parler engine here is Tamil only, not {lang!r}")
        self.load()
        import torch

        assert self._model is not None and self._prompt_tok is not None and self._desc_tok is not None
        desc = self._desc_tok(self.description(voice, speed), return_tensors="pt")
        prompt = self._prompt_tok(text, return_tensors="pt")
        torch.manual_seed(SEED)
        with torch.inference_mode():
            out = self._model.generate(
                input_ids=desc.input_ids,
                attention_mask=desc.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        audio = out.cpu().numpy().squeeze().astype(np.float32)
        return resample_fft(audio, int(self._model.config.sampling_rate), SAMPLE_RATE), SAMPLE_RATE
