"""English -> Hindi/Tamil translation with IndicTrans2, CPU only, loaded then unloaded (H3).

Model: ai4bharat/indictrans2-en-indic-dist-200M (MIT) in models/indictrans2/, read with
local_files_only=True (H2), pre/post-processing by IndicTransToolkit's IndicProcessor (vendored as a
pure-Python port in indic_processor.py, because the PyPI package needs a C compiler on Windows). Code, numbers and glossary terms
are protected with placeholders (protect.py, G5). Narration is translated sentence by sentence so the
sentence count, and therefore the beats, match the English plan.
"""
from __future__ import annotations

import argparse
import copy
import gc
import logging
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..cache.store import load_cached_text, save_cached_text, translate_cache_path, write_json
from ..config import LANGUAGES as SAMPLE_LANGUAGES  # languages the built-in samples come in
from ..config import SAMPLES_DIR, get_settings
from ..planner.fallback import fallback_lesson
from ..planner.validate import validate_lesson
from ..timing.sentences import split_sentences
from .protect import missing_placeholders, protect, restore

log = logging.getLogger("blu.translate")

MODEL_NAME = "indictrans2-en-indic-dist-200M"
SOURCE_CODE = "eng_Latn"
# hi and ta are used now; te, bn and mr are ready for the bonus step.
TARGET_CODES = {"hi": "hin_Deva", "ta": "tam_Taml", "te": "tel_Telu", "bn": "ben_Beng", "mr": "mar_Deva"}
NUM_BEAMS = 4
MAX_LENGTH = 256

# A translation must contain the target script, or it is treated as a failed sentence.
SCRIPTS = {
    "hi": re.compile("[ऀ-ॿ]"), "mr": re.compile("[ऀ-ॿ]"),
    "ta": re.compile("[஀-௿]"), "te": re.compile("[ఀ-౿]"), "bn": re.compile("[ঀ-৿]"),
}
SENTENCE_END = {"hi": "।", "mr": "।", "bn": "।"}  # others end with "."

# Schema limits for the translated fields (shared/schema/lesson.schema.json), in code points.
LIMITS = {"title": 80, "heading": 60, "subheading": 80, "item": 48, "label": 32}
# On-screen limits for diagram text, in visible letters (Tamil vowel signs are separate code points).
VISIBLE_LIMITS = {"item": 24, "label": 16}
SHORT_FIELDS = ("title", "heading", "subheading", "item", "label")  # shown as labels: no full stop

# Diagram items that are code or plain numbers stay as they are.
_CODE_ITEM = re.compile(r"[=()\[\]{}<>_`]|^[\s\d.,:+\-*/%]+$")


class TranslationUnavailable(RuntimeError):
    """The model or its libraries are missing, or the model failed."""


_lock = threading.Lock()
_state: dict[str, Any] = {}


def model_dir() -> Path:
    return get_settings().models_dir / "indictrans2"


def is_available() -> bool:
    return (model_dir() / "config.json").is_file()


def load() -> None:
    """Load tokenizer, model and processor from models/indictrans2/ (CPU, local files only)."""
    with _lock:
        if _state:
            return
        d = model_dir()
        if not (d / "config.json").is_file():
            raise TranslationUnavailable(f"IndicTrans2 not found in {d}; run: python scripts/download_models.py indictrans2")
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            from .indic_processor import IndicProcessor
        except ImportError as exc:
            raise TranslationUnavailable(f"translation libraries missing ({exc.name}); see backend/requirements-models.txt") from exc
        start = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(d, trust_remote_code=True, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(d, trust_remote_code=True, local_files_only=True, torch_dtype=torch.float32)
        model.eval()
        _state.update(torch=torch, tokenizer=tokenizer, model=model, ip=IndicProcessor())
        log.info("IndicTrans2 loaded in %.1fs", time.perf_counter() - start)


def unload() -> None:
    """Release the model so its RAM is free before TTS (H3)."""
    with _lock:
        _state.clear()
    gc.collect()


def _generate(texts: list[str], tgt: str) -> list[str]:
    """One batched beam-search call for all strings."""
    torch, tokenizer, model, ip = _state["torch"], _state["tokenizer"], _state["model"], _state["ip"]
    batch = ip.preprocess_batch(texts, src_lang=SOURCE_CODE, tgt_lang=tgt)
    inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True)
    with torch.inference_mode():
        out = model.generate(**inputs, use_cache=True, min_length=0, max_length=MAX_LENGTH, num_beams=NUM_BEAMS, num_return_sequences=1)
    decoded = tokenizer.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
    return ip.postprocess_batch(decoded, lang=tgt)


def _translate_masked(indices: list[int], texts: list[str], lang: str, use_glossary: bool) -> dict[int, str | None]:
    """Translate texts[i] for i in indices with protection on; None where a placeholder was lost."""
    masked = [protect(texts[i], use_glossary) for i in indices]
    outputs = _generate([m for m, _ in masked], TARGET_CODES[lang])
    result: dict[int, str | None] = {}
    for i, (_, mapping), out in zip(indices, masked, outputs):
        if lang not in SENTENCE_END:  # the model writes in Devanagari; Tamil and Telugu end sentences with "."
            out = out.replace("।", ".")
        lost = missing_placeholders(out, mapping)
        restored = restore(out, mapping)
        ok = not lost and bool(SCRIPTS[lang].search(restored))
        result[i] = restored.strip() if ok else None
    return result


def translate_texts(texts: list[str], target_lang: str, stats: dict[str, int] | None = None) -> list[str]:
    """Translate English strings with protected terms kept (G5); cached per string.

    A string whose placeholders do not survive is retried once with glossary protection off (code and
    numbers still protected); if that fails too, the English string is kept and logged.
    """
    if target_lang not in TARGET_CODES:
        raise ValueError(f"unsupported language {target_lang!r}")
    stats = stats if stats is not None else {}
    results: list[str | None] = [None] * len(texts)
    paths = [translate_cache_path(MODEL_NAME, target_lang, t) for t in texts]
    todo: list[int] = []
    for i, t in enumerate(texts):
        if not t.strip():
            results[i] = t
        elif (hit := load_cached_text(paths[i])) is not None:
            results[i] = hit
            stats["cached"] = stats.get("cached", 0) + 1
        else:
            todo.append(i)
    if todo:
        load()
        first = _translate_masked(todo, texts, target_lang, use_glossary=True)
        retry = [i for i in todo if first[i] is None]
        second = _translate_masked(retry, texts, target_lang, use_glossary=False) if retry else {}
        for i in todo:
            out = first[i] if first[i] is not None else second.get(i)
            if out is None:
                log.warning("translation to %s lost a protected span twice; keeping English: %r", target_lang, texts[i])
                stats["english"] = stats.get("english", 0) + 1
                results[i] = texts[i]
                continue
            stats["retried" if first[i] is None else "translated"] = stats.get("retried" if first[i] is None else "translated", 0) + 1
            results[i] = out
            save_cached_text(paths[i], texts[i], out)
    return [r if r is not None else t for r, t in zip(results, texts)]


def _one_sentence(text: str, lang: str) -> str:
    """Make a translated sentence exactly one sentence for the splitter, ending in the language's stop."""
    pieces = split_sentences(text, lang)
    if len(pieces) > 1:  # the model split one English sentence in two: join them back
        text = ", ".join(p.rstrip(" .।") for p in pieces[:-1]) + ", " + pieces[-1]
    text = text.strip()
    if not re.search(r"[.?!।॥]['\"”’)\]]*$", text):
        text += SENTENCE_END.get(lang, ".")
    return text


def visible_len(text: str) -> int:
    """Letters as the eye counts them: one per grapheme cluster, not per code point."""
    import regex

    return len(regex.findall(r"\X", text))


def is_code_item(item: str) -> bool:
    return bool(_CODE_ITEM.search(item))


def _translate_lesson(lesson: dict[str, Any], lang: str, stats: dict[str, int]) -> dict[str, Any]:
    out = copy.deepcopy(lesson)
    jobs: list[tuple[str, str, Callable[[str], None]]] = []  # (kind, english, setter)

    def add(kind: str, english: str, setter: Callable[[str], None]) -> None:
        jobs.append((kind, english, setter))

    def setter(obj: dict[str, Any], key: str) -> Callable[[str], None]:
        return lambda v: obj.__setitem__(key, v)

    add("title", lesson["title"], setter(out, "title"))
    narration: list[list[str]] = []
    for scene, tr in zip(lesson["scenes"], out["scenes"]):
        add("heading", scene["heading"], setter(tr, "heading"))
        if scene.get("subheading"):
            add("subheading", scene["subheading"], setter(tr, "subheading"))
        for k, item in enumerate(scene.get("items", [])):
            if not is_code_item(item):
                add("item", item, lambda v, tr=tr, k=k: tr["items"].__setitem__(k, v))
        for a_en, a_tr in zip(scene.get("arrows", []), tr.get("arrows", [])):
            if len(a_en.get("label", "")) >= 3:
                add("label", a_en["label"], setter(a_tr, "label"))
        sentences = split_sentences(scene["narration"], "en")
        slots = [""] * len(sentences)
        narration.append(slots)
        for k, s in enumerate(sentences):
            add("sentence", s, lambda v, slots=slots, k=k: slots.__setitem__(k, v))

    translated = translate_texts([e for _, e, _ in jobs], lang, stats)
    for (kind, english, set_value), value in zip(jobs, translated):
        if kind in SHORT_FIELDS and not english.rstrip().endswith((".", "!", "?")):
            value = value.rstrip().rstrip("।.").rstrip()
        too_long = len(value) > LIMITS.get(kind, len(value)) or visible_len(value) > VISIBLE_LIMITS.get(kind, len(value))
        if too_long:
            log.warning("translated %s is too long; keeping English: %r -> %r", kind, english, value)
            value = english
        set_value(value)

    for tr, slots in zip(out["scenes"], narration):
        tr["narration"] = " ".join(_one_sentence(s, lang) for s in slots)
    out["language"] = lang

    for en_scene, tr in zip(lesson["scenes"], out["scenes"]):  # beats depend on this
        n_en, n_tr = len(split_sentences(en_scene["narration"], "en")), len(split_sentences(tr["narration"], lang))
        if n_en != n_tr:
            raise TranslationUnavailable(f"sentence count changed ({n_en} -> {n_tr}) in scene {en_scene['heading']!r}")
    errors = validate_lesson(out)
    if errors:
        raise TranslationUnavailable("translated lesson is invalid: " + "; ".join(errors[:3]))
    return out


def translate_lesson(lesson: dict[str, Any], target_lang: str, keep_loaded: bool = False) -> dict[str, Any]:
    """Translate heading, subheading, narration, title, non-code items and longer arrow labels.

    Code, code-like items and numbers are never translated. If the model is missing or fails, a
    built-in (fallback) lesson uses its pre-translated sample; any other lesson keeps its English text
    and gets meta.translation_fallback = true (G2). The model is unloaded afterwards unless keep_loaded.
    """
    if target_lang == "en" or lesson.get("language") == target_lang:
        return lesson
    meta = lesson.get("meta", {})
    if meta.get("fallback") and target_lang in SAMPLE_LANGUAGES:  # a built-in sample: use its checked translation
        return fallback_lesson(meta.get("topic", ""), lesson.get("level", "beginner"), target_lang, reason=meta.get("reason") or "")
    stats: dict[str, int] = {}
    start = time.perf_counter()
    try:
        out = _translate_lesson(lesson, target_lang, stats)
        log.info("translated lesson to %s in %.1fs %s", target_lang, time.perf_counter() - start, stats)
        return out
    except Exception as exc:  # noqa: BLE001 - any failure falls back (G2)
        log.warning("translation to %s failed: %s", target_lang, exc)
        meta = lesson.get("meta", {})
        if meta.get("fallback"):
            return fallback_lesson(meta.get("topic", ""), lesson.get("level", "beginner"), target_lang,
                                   reason=meta.get("reason") or "Translation is not available, so a pre-translated sample is shown.")
        out = copy.deepcopy(lesson)
        out.setdefault("meta", {"fallback": False})["translation_fallback"] = True
        return out  # still English, so it is voiced in English
    finally:
        if not keep_loaded:
            unload()


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m app.translate.indictrans --sample photosynthesis --lang hi ta [--write]"""
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description="Translate an English lesson with IndicTrans2 (offline).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sample", help="name of shared/samples/<name>.en.json")
    src.add_argument("--lesson", type=Path, help="path to an English lesson.json")
    ap.add_argument("--lang", nargs="+", default=["hi", "ta"], choices=sorted(TARGET_CODES))
    ap.add_argument("--write", action="store_true", help="with --sample: save shared/samples/<name>.<lang>.json")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    import json

    path = SAMPLES_DIR / f"{args.sample}.en.json" if args.sample else args.lesson
    lesson = json.loads(path.read_text(encoding="utf-8"))
    for lang in args.lang:
        start = time.perf_counter()
        out = translate_lesson(lesson, lang, keep_loaded=True)
        took = time.perf_counter() - start
        failed = out.get("language") != lang or out.get("meta", {}).get("translation_fallback")
        print(f"{lang}: {'FAILED, kept English' if failed else 'ok'} in {took:.1f}s")
        if args.write and args.sample and not failed:
            write_json(SAMPLES_DIR / f"{args.sample}.{lang}.json", out)
            print(f"  wrote shared/samples/{args.sample}.{lang}.json")
        elif not args.write:
            print(json.dumps(out, ensure_ascii=False, indent=2))
    unload()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
