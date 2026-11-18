"""Kiwi tokenization and document-level n-grams."""

import re
from collections import Counter

from kiwipiepy import Kiwi

from .config import TrendConfig

CONTENT_TAGS = {"NNG", "NNP", "SL", "SH"}


def clean_surface(form: str, tag: str, config: TrendConfig) -> str:
    token = (form.lower() if tag == "SL" else form).strip()
    if len(token) < 2 or token.lower() in config.stop_words:
        return ""
    if re.fullmatch(r"[\d\W_]+", token) or re.fullmatch(r"[ㄱ-ㅎ]+", token):
        return ""
    return token


def build_kiwi(titles: list[str], config: TrendConfig) -> Kiwi:
    kiwi = Kiwi(num_workers=1)
    seen = Counter()
    for analyzed in kiwi.tokenize(titles):
        for token in analyzed:
            if (
                token.tag == "NNP"
                and re.fullmatch(r"[가-힣]{3}", token.form)
                and token.form not in config.stop_words
            ):
                seen[token.form] += 1
    for word, count in seen.items():
        if count >= config.min_name_count:
            kiwi.add_user_word(word, "NNP", config.user_word_score)
    return kiwi


def content_tokens(analyzed, config: TrendConfig) -> list[str]:
    tokens = []
    alnum = ""

    def emit(token):
        if token and (not tokens or tokens[-1] != token):
            tokens.append(token)

    def flush():
        nonlocal alnum
        if alnum:
            emit(clean_surface(alnum, "SL", config))
            alnum = ""

    for tok in analyzed:
        form = tok.form or ""
        is_digit = tok.tag == "SN" and form.isdigit()
        short_latin = tok.tag == "SL" and len(form) == 1 and form.isascii() and form.isalnum()
        if is_digit or short_latin:
            alnum += form
            continue
        if alnum.isdigit() and tok.tag in {"NNG", "NNP"}:
            emit(clean_surface(alnum + form, "NNG", config))
            alnum = ""
            continue
        flush()
        if tok.tag in CONTENT_TAGS:
            emit(clean_surface(form, tok.tag, config))
    flush()
    return tokens


def ngram_keys(tokens: list[str], max_ngram: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[i : i + width])
        for width in range(1, min(max_ngram, len(tokens)) + 1)
        for i in range(len(tokens) - width + 1)
    }
