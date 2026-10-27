"""Pure-Python port of IndicTransToolkit's IndicProcessor (inference, English -> Indic).

IndicTransToolkit 1.1.1 (MIT, Copyright (c) Varun Gumma) ships this class only as a Cython extension,
which needs a C compiler to install on Windows. This is the same algorithm, unchanged, for the
direction we use: English source in, Indic target out. The model writes every Indic language in
Devanagari; postprocess_batch transliterates it to the target script (e.g. Tamil) and detokenises.
"""
from __future__ import annotations

import regex as re
from indicnlp.tokenize import indic_detokenize
from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator
from sacremoses import MosesPunctNormalizer, MosesTokenizer

FLORES_TO_ISO = {
    "asm_Beng": "as", "ben_Beng": "bn", "eng_Latn": "en", "guj_Gujr": "gu", "hin_Deva": "hi", "kan_Knda": "kn",
    "mal_Mlym": "ml", "mar_Deva": "mr", "npi_Deva": "ne", "ory_Orya": "or", "pan_Guru": "pa", "tam_Taml": "ta",
    "tel_Telu": "te", "urd_Arab": "ur",
}

# Indic digits -> ASCII (Bengali, Gujarati, Kannada, Devanagari, Arabic, Meitei, Oriya, Gurmukhi, Ol Chiki, Persian, Telugu)
_DIGIT_BLOCKS = [0x09E6, 0x0AE6, 0x0CE6, 0x0966, 0x0660, 0xABF0, 0x0B66, 0x0A66, 0x1C50, 0x06F0, 0x0C66]
_DIGITS = {block + d: str(d) for block in _DIGIT_BLOCKS for d in range(10)}

_MULTISPACE = re.compile(r"[ ]{2,}")
_DIGIT_SPACE_PERCENT = re.compile(r"(\d) %")
_DOUBLE_QUOT_PUNC = re.compile(r"\"([,\.]+)")
_DIGIT_NBSP_DIGIT = re.compile(r"(\d) (\d)")
_END_BRACKET_SPACE_PUNC = re.compile(r"\) ([\.!:?;,])")
_URL = re.compile(r"\b(?<![\w/.])(?:(?:https?|ftp)://)?(?:(?:[\w-]+\.)+(?!\.))(?:[\w/\-?#&=%.]+)+(?!\.\w+)\b")
_NUMERAL = re.compile(r"(~?\d+\.?\d*\s?%?\s?-?\s?~?\d+\.?\d*\s?%|~?\d+%|\d+[-\/.,:']\d+[-\/.,:'+]\d+(?:\.\d+)?|\d+[-\/.:'+]\d+(?:\.\d+)?)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}")
_OTHER = re.compile(r"[A-Za-z0-9]*[#|@]\w+")
_PUNC_REPLACEMENTS = [
    (re.compile(r"\r"), ""), (re.compile(r"\(\s*"), "("), (re.compile(r"\s*\)"), ")"), (re.compile(r"\s:\s?"), ":"),
    (re.compile(r"\s;\s?"), ";"), (re.compile(r"[`´‘‚’]"), "'"), (re.compile(r"[„“”«»]"), '"'), (re.compile(r"[–—]"), "-"),
    (re.compile(r"\.\.\."), "..."), (re.compile(r" %"), "%"), (re.compile(r"nº "), "nº "), (re.compile(r" ºC"), " ºC"),
    (re.compile(r" [?!;]"), lambda m: m.group(0).strip()), (re.compile(r", "), ", "),
]
# Ways the model sometimes spells the "ID" of a placeholder in Indic scripts.
_INDIC_FAILURE_CASES = [
    "آی ڈی ", "ꯑꯥꯏꯗꯤ", "आईडी", "आई . डी . ", "आई . डी .", "आई. डी. ", "आई. डी.", "आय. डी. ", "आय. डी.", "आय . डी . ",
    "आय . डी .आइ . डी . ", "आइ . डी .", "आइ. डी. ", "आइ. डी.", "ऐटि", "آئی ڈی ", "ᱟᱭᱰᱤ ᱾", "आयडी", "ऐडि", "आइडि", "ᱟᱭᱰᱤ",
]


class IndicProcessor:
    """preprocess_batch / postprocess_batch as in IndicTransToolkit (inference mode, English source)."""

    def __init__(self) -> None:
        self._maps: list[dict[str, str]] = []
        self._en_tok = MosesTokenizer(lang="en")
        self._en_normalizer = MosesPunctNormalizer()

    @staticmethod
    def _punc_norm(text: str) -> str:
        for pattern, repl in _PUNC_REPLACEMENTS:
            text = pattern.sub(repl, text)
        text = _MULTISPACE.sub(" ", text)
        text = _END_BRACKET_SPACE_PUNC.sub(r")\1", text)
        text = _DIGIT_SPACE_PERCENT.sub(r"\1%", text)
        text = _DOUBLE_QUOT_PUNC.sub(r'\1"', text)
        text = _DIGIT_NBSP_DIGIT.sub(r"\1.\2", text)
        return text.strip()

    @staticmethod
    def _wrap_with_placeholders(text: str) -> tuple[str, dict[str, str]]:
        serial = 1
        entity_map: dict[str, str] = {}
        for pattern in (_EMAIL, _URL, _NUMERAL, _OTHER):
            for match in set(pattern.findall(text)):
                if pattern is _URL and len(match.replace(".", "")) < 4:
                    continue
                if pattern is _NUMERAL and len(match.replace(" ", "").replace(".", "").replace(":", "")) < 4:
                    continue
                for fmt in ("<ID{}>", "< ID{} >", "[ID{}]", "[ ID{} ]", "[ID {}]", "<ID{}]", "< ID{}]", "<ID{} ]"):
                    entity_map[fmt.format(serial)] = match
                    entity_map[fmt.lower().format(serial)] = match
                for case in _INDIC_FAILURE_CASES:
                    for fmt in ("<{c}{n}>", "< {c}{n} >", "< {c} {n} >", "<{c} {n}]", "< {c} {n} ]", "[{c}{n}]", "[{c} {n}]",
                                "[ {c}{n} ]", "[ {c} {n} ]", "{c} {n}", "{c}{n}"):
                        entity_map[fmt.format(c=case, n=serial)] = match
                text = text.replace(match, f"<ID{serial}>")
                serial += 1
        text = re.sub(r"\s+", " ", text).replace(">/", ">").replace("]/", "]")
        return text, entity_map

    def preprocess_batch(self, batch: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        if src_lang != "eng_Latn":
            raise ValueError("this port only handles English source text")
        self._maps = []
        out = []
        for sent in batch:
            sent = self._punc_norm(sent).translate(_DIGITS)
            sent, entity_map = self._wrap_with_placeholders(sent)
            self._maps.append(entity_map)
            tokens = self._en_tok.tokenize(self._en_normalizer.normalize(sent.strip()), escape=False)
            out.append(f"{src_lang} {tgt_lang} {' '.join(tokens).strip()}")
        return out

    def postprocess_batch(self, sents: list[str], lang: str) -> list[str]:
        iso = FLORES_TO_ISO.get(lang, "hi")
        results = []
        for sent, entity_map in zip(sents, self._maps):
            for k, v in entity_map.items():
                sent = sent.replace(k, v)
            sent = UnicodeIndicTransliterator.transliterate(sent, "hi", iso)
            results.append(indic_detokenize.trivial_detokenize(sent, iso))
        self._maps = []
        return results
