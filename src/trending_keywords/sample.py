"""Access the sample bundled in both source and wheel distributions."""

import json
from importlib.resources import files


def load_sample() -> tuple[list[dict], dict]:
    root = files("trending_keywords").joinpath("data")
    metadata = json.loads(root.joinpath("sample_metadata.json").read_text(encoding="utf-8"))
    posts = [
        json.loads(line)
        for line in root.joinpath("sample_posts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return posts, metadata
