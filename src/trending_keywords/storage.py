"""Explicit I/O adapters; input databases are always opened read-only."""

import datetime as dt
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

INPUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    idx TEXT NOT NULL,
    community TEXT NOT NULL,
    title TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    reg_date TEXT NOT NULL,
    PRIMARY KEY (community, idx)
);
CREATE INDEX IF NOT EXISTS idx_posts_reg_date ON posts(reg_date);
"""

RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_runs (
    run_id TEXT PRIMARY KEY,
    analysis_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trend_results (
    run_id TEXT NOT NULL REFERENCES trend_runs(run_id),
    rank INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    score REAL NOT NULL,
    post_refs_json TEXT NOT NULL,
    PRIMARY KEY (run_id, rank)
);
"""


def load_jsonl(path: str | Path) -> list[dict]:
    records = []
    with Path(path).open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {number}: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"JSONL line {number} must contain an object")
            records.append(record)
    return records


def read_posts(path: str | Path, start: dt.datetime, end: dt.datetime) -> list[dict]:
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(posts)")}
        required = {"idx", "title", "community", "views", "reg_date"}
        missing = required - columns
        if missing:
            raise ValueError("posts table is missing columns: " + ", ".join(sorted(missing)))
        lower = start.strftime("%Y-%m-%d %H:%M:%S")
        upper = (end + dt.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute(
            "SELECT idx, title, community, views, reg_date FROM posts "
            "WHERE reg_date >= ? AND reg_date < ? ORDER BY reg_date, community, idx",
            (lower, upper),
        ).fetchall()
        return [dict(row) for row in rows]


def init_database(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.executescript(INPUT_SCHEMA)


def save_report(path: str | Path, report: dict) -> str:
    """Append one complete run, including an empty run, in one transaction."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, ensure_ascii=False, allow_nan=False)
    run_id = uuid.uuid4().hex
    created_at = dt.datetime.now(dt.timezone.utc).isoformat()
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(RESULT_SCHEMA)
        with db:
            db.execute(
                "INSERT INTO trend_runs VALUES (?, ?, ?, ?)",
                (run_id, report["analysis_at"], created_at, report_json),
            )
            db.executemany(
                "INSERT INTO trend_results VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        row["rank"],
                        row["keyword"],
                        row["score"],
                        json.dumps(row["post_refs"], ensure_ascii=False),
                    )
                    for row in report["keywords"]
                ],
            )
    return run_id
