#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persian text preprocessing for evaluation.

Normalization follows common Persian NLP conventions (Mirzadeh's normalize.py
style): unify Arabic/Persian letters, unify digits, normalize ZWNJ, trim.
"""
import re

_TRANSLATE = str.maketrans({
    "ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا",
    "ؤ": "و", "ئ": "ی", "ٱ": "ا", "ى": "ی", "ں": "ن", "۰": "0", "۱": "1",
    "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8",
    "۹": "9", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5",
    "٦": "6", "٧": "7", "٨": "8", "٩": "9", "﷼": "ریال",
})

ZWNJ = "\u200c"


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.translate(_TRANSLATE)
    text = text.replace(ZWNJ, " ")           # ZWNJ → space for matching
    text = re.sub(r"[\u064B-\u0652\u06D6-\u06ED\u0670\u0671]", "", text)  # diacritics
    text = re.sub(r"[\s\u200e\u200f\u200d\u2069]+", " ", text)            # collapse spaces/hidden
    text = re.sub(r"[،؛:.]", " ", text)
    return text.strip().lower()


def norm_tokens(text: str) -> set:
    return {t for t in normalize(text).split() if len(t) >= 2}


def jaccard(gold: str, pred: str) -> float:
    g = norm_tokens(gold)
    p = norm_tokens(pred)
    if not g or not p:
        return 0.0
    return len(g & p) / len(g | p)