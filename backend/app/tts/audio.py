"""Per-sentence audio clean-up shared by every engine: resample, peak-normalise, trim silence."""
from __future__ import annotations

import numpy as np

from .base import SAMPLE_RATE

PEAK_DBFS = -1.0  # every sentence is normalised to this peak
SILENCE_DBFS = -45.0  # a 10 ms frame quieter than this (RMS, after normalising) counts as silence
KEEP_PAD_S = 0.03  # silence kept around the speech so soft onsets and tails are not clipped
FADE_S = 0.004  # edge fade that prevents clicks at the cut
FRAME_S = 0.010
POSTPROCESS_VERSION = "pp1"  # part of the TTS cache key; bump when this module changes the audio


def resample_fft(samples: np.ndarray, sr_in: int, sr_out: int = SAMPLE_RATE) -> np.ndarray:
    """Band-limited resample by spectrum cropping/padding (no scipy needed); mono float32."""
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr_in == sr_out or len(x) < 2:
        return x
    n_out = round(len(x) * sr_out / sr_in)
    spectrum = np.fft.rfft(x.astype(np.float64))
    keep = n_out // 2 + 1
    spectrum = spectrum[:keep] if keep <= len(spectrum) else np.pad(spectrum, (0, keep - len(spectrum)))
    y = np.fft.irfft(spectrum, n_out) * (n_out / len(x))
    return y.astype(np.float32)


def normalise_peak(samples: np.ndarray, peak_dbfs: float = PEAK_DBFS) -> np.ndarray:
    """Scale so the largest absolute sample sits at peak_dbfs. Silence is returned unchanged."""
    x = np.nan_to_num(np.asarray(samples, dtype=np.float32))
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak < 1e-6:
        return x
    return (x * (10.0 ** (peak_dbfs / 20.0) / peak)).astype(np.float32)


def trim_silence(
    samples: np.ndarray,
    sr: int = SAMPLE_RATE,
    threshold_dbfs: float = SILENCE_DBFS,
    pad_s: float = KEEP_PAD_S,
) -> np.ndarray:
    """Cut leading/trailing silence, keeping pad_s on both sides. All-silent input is returned as is."""
    x = np.asarray(samples, dtype=np.float32)
    frame = max(1, round(FRAME_S * sr))
    n_frames = len(x) // frame
    if n_frames == 0:
        return x
    rms = np.sqrt(np.mean(x[: n_frames * frame].reshape(n_frames, frame) ** 2, axis=1))
    loud = np.flatnonzero(rms > 10.0 ** (threshold_dbfs / 20.0))
    if len(loud) == 0:
        return x
    pad = round(pad_s * sr)
    start = max(0, int(loud[0]) * frame - pad)
    end = min(len(x), (int(loud[-1]) + 1) * frame + pad)
    return x[start:end]


def fade_edges(samples: np.ndarray, sr: int = SAMPLE_RATE, fade_s: float = FADE_S) -> np.ndarray:
    x = np.array(samples, dtype=np.float32)
    n = min(round(fade_s * sr), len(x) // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def finalize_sentence(samples: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Normalise to -1 dBFS peak, trim edge silence, fade the cut. Run before timing (the length is final)."""
    return fade_edges(trim_silence(normalise_peak(samples), sr), sr)
