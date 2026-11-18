"""Build a deterministic topic-projected sample from a user-supplied SQLite DB.

No source paths, raw titles, original IDs, links, or source-label mappings are
written to the output. The source is opened read-only by the storage adapter.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from trending_keywords.core import parse_datetime
from trending_keywords.storage import read_posts

DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "trending_keywords" / "data"


def build_sample(database: Path, at: dt.datetime, destination: Path) -> dict:
    vocabulary = json.loads((DATA_DIR / "sample_vocabulary.json").read_text(encoding="utf-8"))
    words = vocabulary["anchors"] + vocabulary["events"]
    canonical = {word.casefold(): word for word in words}
    pattern = re.compile(
        "|".join(
            (r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])")
            if word.isascii()
            else re.escape(word)
            for word in sorted(words, key=lambda word: (-len(word), word))
        ),
        re.IGNORECASE,
    )
    start = at - dt.timedelta(hours=16, days=14)
    boundary = at - dt.timedelta(hours=16)
    source = [
        post
        for post in read_posts(database, start, at)
        if start < parse_datetime(post["reg_date"]) <= at
    ]
    labels = {
        name: f"community_{i + 1}"
        for i, name in enumerate(sorted({p["community"] for p in source}))
    }
    posts = []
    for post in source:
        terms = list(
            dict.fromkeys(
                canonical[match.group().casefold()] for match in pattern.finditer(post["title"])
            )
        )
        if len(terms) < 2 or not set(terms).intersection(vocabulary["anchors"]):
            continue
        posts.append(
            {
                "idx": f"sample_{len(posts) + 1:05}",
                "community": labels[post["community"]],
                "title": " ".join(terms[:12]),
                "views": post["views"],
                "reg_date": parse_datetime(post["reg_date"]).isoformat(sep=" "),
            }
        )
    if not posts:
        raise ValueError("No sample posts matched the vocabulary and date range")
    destination.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(post, ensure_ascii=False) + "\n" for post in posts)
    # Explicit LF and UTF-8 make the checksum reproducible across operating systems.
    encoded = payload.encode("utf-8")
    (destination / "sample_posts.jsonl").write_bytes(encoded)
    metadata = {
        "schema_version": 1,
        "kind": "real-data-derived-topic-projection",
        "analysis_at": at.isoformat(sep=" "),
        "window_hours": 16,
        "background_days": 14,
        "source_window_posts": len(source),
        "sample_posts": len(posts),
        "recent_posts": sum(parse_datetime(p["reg_date"]) > boundary for p in posts),
        "background_posts": sum(parse_datetime(p["reg_date"]) <= boundary for p in posts),
        "communities": dict(sorted(Counter(p["community"] for p in posts).items())),
        "first_post_at": min(p["reg_date"] for p in posts),
        "last_post_at": max(p["reg_date"] for p in posts),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "transformation": "Allowlisted sports/esports terms in source order (max 12 distinct terms); at least two terms including an anchor. Views and timestamps preserved; IDs replaced and communities pseudonymized. No random sampling.",
        "limitations": "Selected and projected titles are for software demonstration, not a representative corpus, factual news source, or accuracy benchmark.",
    }
    (destination / "sample_metadata.json").write_bytes(
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--at", type=parse_datetime, required=True)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    print(json.dumps(build_sample(args.db, args.at, args.output_dir), ensure_ascii=False, indent=2))
