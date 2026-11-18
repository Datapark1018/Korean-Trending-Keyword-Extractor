"""Validated, per-analysis settings; no mutable module-level configuration."""

import math
from dataclasses import asdict, dataclass

DEFAULT_STOP_WORDS = frozenset(
    {
        "싱글벙글",
        "단독",
        "속보",
        "스압",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "manhwa",
        "근황",
        "상황",
        "실시간",
        "이유",
        "webp",
        "mp4",
        "twt",
        "gifv",
        "오피셜",
        "vs",
    }
)


@dataclass(frozen=True)
class TrendConfig:
    window_hours: float = 16
    background_days: float = 14
    half_life_hours: float = 8
    min_communities: int = 2
    min_posts_per_community: int = 2
    max_ngram: int = 3
    min_posts: int = 4
    min_z: float = 3.0
    min_lift: float = 3.5
    min_npmi: float = 0.25
    prior_count: float = 1.0
    subsume_coverage: float = 0.6
    subsume_score_ratio: float = 0.6
    user_word_score: float = 10.0
    min_name_count: int = 3
    top_n: int = 40
    stop_words: frozenset[str] = DEFAULT_STOP_WORDS

    def __post_init__(self):
        positive = ("window_hours", "background_days", "half_life_hours", "prior_count")
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and greater than zero")
        integers = (
            "min_communities",
            "min_posts_per_community",
            "max_ngram",
            "min_posts",
            "min_name_count",
            "top_n",
        )
        for name in integers:
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_ngram > 3:
            raise ValueError("max_ngram must be between 1 and 3")
        for name in ("min_npmi", "subsume_coverage", "subsume_score_ratio"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in ("min_z", "min_lift", "user_word_score"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if isinstance(self.stop_words, str) or any(not isinstance(w, str) for w in self.stop_words):
            raise ValueError("stop_words must be a collection of strings")
        object.__setattr__(self, "stop_words", frozenset(w.lower() for w in self.stop_words))

    def to_dict(self) -> dict:
        values = asdict(self)
        values["stop_words"] = sorted(self.stop_words)
        return values
