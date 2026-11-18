"""Command-line interface: demo, analyze, and init-db."""

import argparse
import datetime as dt
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import DEFAULT_STOP_WORDS, TrendConfig
from .core import analyze_posts, parse_datetime
from .sample import load_sample
from .storage import init_database, load_jsonl, read_posts, save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emerging keywords from Korean post titles.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser(
        "demo", help="Analyze the bundled, DB-derived sample at its fixed date"
    )
    analyze = commands.add_parser("analyze", help="Analyze your JSONL or SQLite data (read-only)")
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="UTF-8 JSONL file")
    source.add_argument("--db", type=Path, help="SQLite database with a posts table")
    analyze.add_argument("--at", help="Local analysis timestamp, e.g. '2026-11-09 23:52:00'")
    for command in (demo, analyze):
        command.add_argument("--format", choices=("table", "json"), default="table")
        command.add_argument(
            "--output", type=Path, help="Write output to this file instead of stdout"
        )
        command.add_argument(
            "--save-db", type=Path, help="Append a run to a separate results SQLite DB"
        )
        command.add_argument("--top", type=int, default=40, help="Maximum number of keywords")
    analyze.add_argument("--window-hours", type=float, default=16)
    analyze.add_argument("--background-days", type=float, default=14)
    analyze.add_argument("--half-life-hours", type=float, default=8)
    analyze.add_argument("--min-lift", type=float, default=3.5)
    analyze.add_argument("--min-z", type=float, default=3.0)
    analyze.add_argument("--min-npmi", type=float, default=0.25)
    analyze.add_argument("--min-posts", type=int, default=4)
    analyze.add_argument("--min-communities", type=int, default=2)
    analyze.add_argument("--min-posts-per-community", type=int, default=2)
    analyze.add_argument("--stopwords", type=Path, help="Additional UTF-8 stop words, one per line")
    init = commands.add_parser(
        "init-db", help="Create the input posts schema; existing rows are kept"
    )
    init.add_argument("path", type=Path)
    return parser


def render_table(report: dict) -> str:
    lines = [
        f"at={report['analysis_at']}  recent={report['recent_posts']}  background={report['background_posts']}",
        "rank  score     lift    posts  keyword",
    ]
    for row in report["keywords"]:
        lines.append(
            f"{row['rank']:>4}  {row['score']:>8.2f}  {row['lift']:>6.1f}  {row['posts']:>5}  {row['keyword']}"
        )
    if not report["keywords"]:
        lines.append("No keywords matched. Check data coverage, views, and filtering thresholds.")
    return "\n".join(lines) + "\n"


def _check_output_paths(args):
    def same_file(first, second):
        if first is None or second is None:
            return False
        return first == second or (first.exists() and second.exists() and first.samefile(second))

    source = getattr(args, "input", None) or getattr(args, "db", None)
    source = source.resolve() if source else None
    output = args.output.resolve() if args.output else None
    saved = args.save_db.resolve() if args.save_db else None
    if same_file(source, output) or same_file(source, saved):
        raise ValueError("Output paths must differ from the input; use a separate results database")
    if same_file(output, saved):
        raise ValueError("--output and --save-db must use different paths")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init-db":
            init_database(args.path)
            print(f"Input schema ready: {args.path}")
            return 0
        _check_output_paths(args)
        config = TrendConfig(top_n=args.top)
        if args.command == "demo":
            posts, metadata = load_sample()
            now = parse_datetime(metadata["analysis_at"])
        else:
            now = parse_datetime(args.at) if args.at else dt.datetime.now()
            names = (
                "window_hours",
                "background_days",
                "half_life_hours",
                "min_lift",
                "min_z",
                "min_npmi",
                "min_posts",
                "min_communities",
                "min_posts_per_community",
            )
            config = replace(config, **{name: getattr(args, name) for name in names})
            if args.stopwords:
                words = {
                    line.strip().lower()
                    for line in args.stopwords.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                }
                config = replace(config, stop_words=DEFAULT_STOP_WORDS | words)
            if args.input:
                posts = load_jsonl(args.input)
            else:
                start = now - dt.timedelta(hours=config.window_hours, days=config.background_days)
                posts = read_posts(args.db, start, now)
        report = analyze_posts(posts, now=now, config=config)
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            if args.format == "json"
            else render_table(report)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(rendered)
        if args.save_db:
            run_id = save_report(args.save_db, report)
            print(f"Saved run {run_id} to {args.save_db}", file=sys.stderr)
        return 0
    except (ValueError, OSError, OverflowError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
