"""Populate a disposable input DB with the bundled sample and analyze it."""

import argparse
import datetime as dt
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from trending_keywords import analyze_posts
from trending_keywords.cli import render_table
from trending_keywords.sample import load_sample
from trending_keywords.storage import init_database, read_posts, save_report


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("local"))
    args = parser.parse_args()
    posts, metadata = load_sample()
    input_path = args.directory / "sample.sqlite3"
    if input_path.exists():
        parser.error(f"{input_path} already exists; choose a new --directory")
    init_database(input_path)
    with closing(sqlite3.connect(input_path)) as db, db:
        db.executemany(
            "INSERT INTO posts (idx, community, title, views, reg_date) VALUES (:idx, :community, :title, :views, :reg_date)",
            posts,
        )
    now = dt.datetime.fromisoformat(metadata["analysis_at"])
    loaded = read_posts(input_path, now - dt.timedelta(days=14, hours=16), now)
    report = analyze_posts(loaded, now=now)
    print(render_table(report), end="")
    print("Saved run:", save_report(args.directory / "results.sqlite3", report))


if __name__ == "__main__":
    main()
