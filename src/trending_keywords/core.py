"""Pure analysis: no filesystem access and no mutation of caller-owned posts."""

import datetime as dt
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from statistics import median

from .config import TrendConfig
from .tokenization import build_kiwi, content_tokens, ngram_keys


def parse_datetime(value) -> dt.datetime:
    """Accept ISO local timestamps; reject offsets instead of silently discarding them."""
    try:
        parsed = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid timestamp: {value!r}; expected YYYY-MM-DD HH:MM:SS") from exc
    if parsed.tzinfo is not None:
        raise ValueError("Use timezone-naive timestamps in one consistent timezone")
    return parsed


def normalize_posts(posts: Iterable[Mapping]) -> list[dict]:
    normalized = []
    for index, post in enumerate(posts):
        if not isinstance(post, Mapping):
            raise ValueError(f"Post {index} must be an object")
        title, community = post.get("title"), post.get("community")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Post {index} needs a non-empty title")
        if not isinstance(community, str) or not community.strip():
            raise ValueError(f"Post {index} needs a non-empty community")
        try:
            views = float(post.get("views") or 0)
        except (ValueError, TypeError, OverflowError):
            views = 0.0
        if not math.isfinite(views) or views < 0:
            views = 0.0
        normalized.append(
            {
                "idx": str(post.get("idx", index)),
                "title": title,
                "community": community.strip(),
                "views": views,
                "reg_date": parse_datetime(post.get("reg_date")),
            }
        )
    return normalized


def community_view_medians(posts: list[dict]) -> dict[str, float]:
    grouped = defaultdict(list)
    for post in posts:
        grouped[post["community"]].append(post["views"])
    global_median = median([p["views"] for p in posts]) if posts else 1.0
    return {
        name: median(values) if len(values) >= 5 else global_median
        for name, values in grouped.items()
    }


def post_weight(post: dict, medians: dict, now: dt.datetime, config: TrendConfig) -> float:
    baseline = max(medians.get(post["community"], 1.0), 1.0)
    view_factor = min(math.log1p(post["views"]) / math.log1p(baseline), 3.0)
    age_hours = max((now - post["reg_date"]).total_seconds() / 3600, 0.0)
    return view_factor * 2 ** (-age_hours / config.half_life_hours)


def npmi(key, unigram_df, joint_df, n_docs) -> float:
    if len(key) == 1:
        return 1.0
    if not 0 < joint_df < n_docs:
        return 0.0
    log_joint = math.log(joint_df / n_docs)
    independent = sum(math.log(unigram_df[(token,)] / n_docs) for token in key)
    # n-way normalization: perfect co-occurrence is 1 for bigrams and trigrams.
    return (log_joint - independent) / (-(len(key) - 1) * log_joint)


def burst_stats(y, n_recent, background_df, n_background, prior_count=1.0):
    expected = n_recent * (background_df + prior_count) / (n_background + prior_count)
    if expected <= 0:
        return 0.0, 0.0, 0.0
    excess = y - expected
    return excess / math.sqrt(expected), y / expected, excess


def community_balance(counts) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    if len(counts) == 1:
        return 1.0
    return -sum((count / total) * math.log(count / total) for count in counts.values()) / math.log(
        len(counts)
    )


def drop_subsumed(rows: list[dict], config: TrendConfig) -> list[dict]:
    dropped = set()
    for i, short in enumerate(rows):
        for long in rows:
            width = len(short["tokens"])
            if (
                width >= len(long["tokens"])
                or long["score"] < short["score"] * config.subsume_score_ratio
            ):
                continue
            if not any(
                long["tokens"][j : j + width] == short["tokens"]
                for j in range(len(long["tokens"]) - width + 1)
            ):
                continue
            overlap = len(set(short["post_indices"]) & set(long["post_indices"])) / short["posts"]
            if overlap >= config.subsume_coverage:
                dropped.add(i)
                break
    return [row for i, row in enumerate(rows) if i not in dropped]


def _rank(recent: list[dict], background_titles: list[str], now, config) -> list[dict]:
    if not recent or not background_titles:
        return []
    medians = community_view_medians(recent)
    weights = [post_weight(post, medians, now, config) for post in recent]
    total_weight = sum(weights)
    if total_weight <= 0:
        return []
    kiwi = build_kiwi([p["title"] for p in recent], config)
    recent_counts = defaultdict(lambda: {"weight": 0.0, "indices": [], "communities": Counter()})
    for index, analyzed in enumerate(kiwi.tokenize([p["title"] for p in recent])):
        for key in ngram_keys(content_tokens(analyzed, config), config.max_ngram):
            bucket = recent_counts[key]
            bucket["weight"] += weights[index]
            bucket["indices"].append(index)
            bucket["communities"][recent[index]["community"]] += 1
    background_counts = Counter()
    for analyzed in kiwi.tokenize(background_titles):
        background_counts.update(ngram_keys(content_tokens(analyzed, config), config.max_ngram))
    unigram_df = {key: len(item["indices"]) for key, item in recent_counts.items() if len(key) == 1}
    rows = []
    for key, item in recent_counts.items():
        count = len(item["indices"])
        strong = sum(n >= config.min_posts_per_community for n in item["communities"].values())
        if count < config.min_posts or strong < config.min_communities:
            continue
        phrase = npmi(key, unigram_df, count, len(recent))
        if len(key) > 1 and phrase < config.min_npmi:
            continue
        bg = background_counts[key]
        z, lift, excess = burst_stats(
            item["weight"], total_weight, bg, len(background_titles), config.prior_count
        )
        if z < config.min_z or lift < config.min_lift or excess <= 0:
            continue
        balance = community_balance(item["communities"])
        rows.append(
            {
                "keyword": " ".join(key),
                "tokens": list(key),
                "n": len(key),
                "score": excess * math.log(lift) * (0.4 + 0.6 * balance),
                "z": z,
                "lift": lift,
                "excess": excess,
                "npmi": phrase,
                "balance": balance,
                "posts": count,
                "weighted_posts": item["weight"],
                "background_posts": bg,
                "communities": dict(sorted(item["communities"].items())),
                "post_indices": item["indices"],
                "post_refs": [
                    {"community": recent[i]["community"], "idx": recent[i]["idx"]}
                    for i in item["indices"]
                ],
            }
        )
    rows.sort(key=lambda row: (-row["score"], -row["posts"], row["keyword"]))
    return [
        dict(rank=rank, **row)
        for rank, row in enumerate(drop_subsumed(rows, config)[: config.top_n], 1)
    ]


def trending_keywords(recent_posts, background_posts, now=None, config=None) -> list[dict]:
    """Rank pre-partitioned posts. Background entries only require a title.

    The caller supplies disjoint windows. Results are JSON-compatible and include
    exact (community, idx) references; input dictionaries are never modified.
    """
    config = config or TrendConfig()
    now = parse_datetime(now if now is not None else dt.datetime.now())
    recent = normalize_posts(recent_posts)
    titles = []
    for index, post in enumerate(background_posts):
        if (
            not isinstance(post, Mapping)
            or not isinstance(post.get("title"), str)
            or not post["title"].strip()
        ):
            raise ValueError(f"Background post {index} needs a non-empty title")
        titles.append(post["title"])
    return _rank(recent, titles, now, config)


def analyze_posts(posts, now=None, config=None) -> dict:
    """Split posts into bounded time windows and return a serializable report."""
    config = config or TrendConfig()
    now = parse_datetime(now if now is not None else dt.datetime.now())
    recent_start = now - dt.timedelta(hours=config.window_hours)
    background_start = recent_start - dt.timedelta(days=config.background_days)
    normalized = normalize_posts(posts)
    recent = [p for p in normalized if recent_start < p["reg_date"] <= now]
    background = [p for p in normalized if background_start < p["reg_date"] <= recent_start]
    return {
        "schema_version": 1,
        "analysis_at": now.isoformat(sep=" "),
        "recent_start": recent_start.isoformat(sep=" "),
        "background_start": background_start.isoformat(sep=" "),
        "recent_posts": len(recent),
        "background_posts": len(background),
        "config": config.to_dict(),
        "keywords": _rank(recent, [p["title"] for p in background], now, config),
    }
