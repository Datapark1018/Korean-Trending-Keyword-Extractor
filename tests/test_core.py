import copy
import datetime as dt
import json
import math
from dataclasses import replace

import pytest

from trending_keywords import TrendConfig, analyze_posts, trending_keywords
from trending_keywords.core import (
    community_view_medians,
    drop_subsumed,
    normalize_posts,
    npmi,
    parse_datetime,
    post_weight,
)
from trending_keywords.tokenization import ngram_keys

NOW = dt.datetime(2026, 1, 15, 12)


def post(title="일상 소식", community="a", views=100, age=1, idx="1"):
    return {
        "idx": idx,
        "title": title,
        "community": community,
        "views": views,
        "reg_date": NOW - dt.timedelta(hours=age),
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"half_life_hours": 0},
        {"window_hours": -1},
        {"prior_count": 0},
        {"min_lift": math.inf},
        {"min_z": math.nan},
        {"top_n": 0},
        {"min_npmi": 1.1},
        {"max_ngram": 4},
        {"min_posts": 2.5},
        {"stop_words": "속보"},
    ],
)
def test_invalid_config(changes):
    with pytest.raises(ValueError):
        TrendConfig(**changes)


def test_half_life_and_median():
    normalized = normalize_posts([post(age=0), post(age=8)])
    config = TrendConfig()
    medians = community_view_medians(normalized)
    assert post_weight(normalized[1], medians, NOW, config) == pytest.approx(0.5)
    assert post_weight(normalized[0], medians, NOW, config) == pytest.approx(1.0)
    assert community_view_medians(normalize_posts([post(views=10), post(views=30)])) == {"a": 20}


@pytest.mark.parametrize("views", [None, "unknown", -3, float("nan"), float("inf")])
def test_invalid_views_are_zero_without_mutation(views):
    original = post(views=views)
    assert normalize_posts([original])[0]["views"] == 0
    assert "_views" not in original


@pytest.mark.parametrize("timestamp", ["garbage", None, "2026-01-15T12:00:00+09:00"])
def test_invalid_or_aware_dates_rejected(timestamp):
    with pytest.raises(ValueError):
        parse_datetime(timestamp)


def test_window_boundaries_and_future_posts():
    # No positive weight -> exercise partitioning without loading a language model.
    posts = [post(views=0, age=age) for age in (-1, 0, 16, 16.0001, 16 + 14 * 24)]
    report = analyze_posts(posts, now=NOW)
    assert report["recent_posts"] == 1
    assert report["background_posts"] == 2
    assert report["keywords"] == []
    json.dumps(report, allow_nan=False)


def test_document_frequency_and_npmi():
    assert ngram_keys(["우주", "우주"], 3) == {("우주",), ("우주", "우주")}
    assert npmi(("a", "b", "c"), {("a",): 2, ("b",): 2, ("c",): 2}, 2, 8) == pytest.approx(1)


def test_specific_phrase_subsumes_short_keyword():
    rows = [
        {"tokens": ["망원경"], "score": 10, "post_indices": [0, 1, 2, 3], "posts": 4},
        {"tokens": ["우주", "망원경"], "score": 8, "post_indices": [0, 1, 2], "posts": 3},
    ]
    assert drop_subsumed(rows, TrendConfig()) == [rows[1]]


def test_real_tokenization_trend_and_exact_references():
    titles = [
        "우주 망원경 관측 성공",
        "우주 망원경 사진 공개",
        "우주 망원경 연구 발표",
        "우주 망원경 성능 개선",
        "주말 산책 코스 추천",
        "점심 메뉴 추천",
        "겨울 출근길 날씨",
        "새로운 요리 도전",
    ]
    recent = [
        post(title, community="a" if i % 2 == 0 else "b", idx=str(i // 2))
        for i, title in enumerate(titles)
    ]
    original = copy.deepcopy(recent)
    background = [{"title": title} for title in titles[4:7] * 40]
    rows = trending_keywords(recent, background, now=NOW)
    assert rows[0]["keyword"] == "우주 망원경"
    assert rows[0]["posts"] == 4
    assert rows[0]["post_indices"] == [0, 1, 2, 3]
    assert {tuple(ref.values()) for ref in rows[0]["post_refs"]} == {
        ("a", "0"),
        ("b", "0"),
        ("a", "1"),
        ("b", "1"),
    }
    assert recent == original
    json.dumps(rows, allow_nan=False)
    single = [dict(p, community="only") for p in recent]
    assert trending_keywords(single, background, now=NOW) == []
    relaxed = trending_keywords(
        single, background, now=NOW, config=replace(TrendConfig(), min_communities=1)
    )
    assert relaxed[0]["balance"] == 1


def test_empty_and_zero_weight_inputs():
    assert trending_keywords([], [], now=NOW) == []
    assert trending_keywords([post(views=0)] * 4, [{"title": "과거 뉴스"}], now=NOW) == []
