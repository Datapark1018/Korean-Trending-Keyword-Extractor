import copy
import datetime as dt
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from trending_keywords import analyze_posts
from trending_keywords.cli import main
from trending_keywords.sample import load_sample
from trending_keywords.storage import init_database, load_jsonl, read_posts, save_report


def test_sqlite_read_only_and_boundaries(tmp_path):
    path = tmp_path / "input.sqlite3"
    init_database(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.executemany(
            "INSERT INTO posts VALUES (?, ?, ?, ?, ?)",
            [
                ("1", "a", "과거 뉴스", 0, "2026-01-14 20:00:00"),
                ("2", "a", "현재 뉴스", 0, "2026-01-15 12:00:00.000000"),
                ("3", "a", "미래 뉴스", 0, "2026-01-15 12:00:00.000001"),
            ],
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    now = dt.datetime(2026, 1, 15, 12)
    report = analyze_posts(read_posts(path, now - dt.timedelta(days=15), now), now=now)
    assert (report["recent_posts"], report["background_posts"]) == (1, 1)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with pytest.raises(FileNotFoundError):
        read_posts(tmp_path / "missing.sqlite3", now, now)
    assert not (tmp_path / "missing.sqlite3").exists()


def test_saved_runs_are_atomic_and_include_empty_results(tmp_path):
    path = tmp_path / "results.sqlite3"
    report = {
        "analysis_at": "2026-01-15 12:00:00",
        "keywords": [
            {
                "rank": 1,
                "keyword": "우주 망원경",
                "score": 12.5,
                "post_refs": [{"community": "a", "idx": "1"}, {"community": "b", "idx": "1"}],
            }
        ],
    }
    first = save_report(path, report)
    empty = save_report(path, dict(report, keywords=[]))
    assert first != empty
    invalid = copy.deepcopy(report)
    invalid["keywords"] *= 2
    with pytest.raises(sqlite3.IntegrityError):
        save_report(path, invalid)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT COUNT(*) FROM trend_runs").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM trend_results").fetchone()[0] == 1
        stored = json.loads(db.execute("SELECT post_refs_json FROM trend_results").fetchone()[0])
        assert stored == report["keywords"][0]["post_refs"]


def test_jsonl_errors_identify_line(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{}\nnot json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_jsonl(path)


def test_cli_does_not_overwrite_input(tmp_path):
    path = tmp_path / "posts.jsonl"
    path.write_text("", encoding="utf-8")
    for flag in ("--output", "--save-db"):
        with pytest.raises(SystemExit) as error:
            main(["analyze", "--input", str(path), flag, str(path)])
        assert error.value.code == 2
    assert path.read_text() == ""


def test_cli_empty_json_and_invalid_settings(tmp_path, capsys):
    path = tmp_path / "posts.jsonl"
    path.write_text("", encoding="utf-8")
    assert (
        main(["analyze", "--input", str(path), "--at", "2026-01-15 12:00:00", "--format", "json"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["keywords"] == []
    with pytest.raises(SystemExit) as error:
        main(["analyze", "--input", str(path), "--half-life-hours", "0"])
    assert error.value.code == 2


def test_cli_rejects_hardlink_to_input(tmp_path):
    source, output = tmp_path / "source.jsonl", tmp_path / "alias.jsonl"
    source.write_text("", encoding="utf-8")
    try:
        os.link(source, output)
    except OSError:
        pytest.skip("Hard links unavailable on this filesystem")
    with pytest.raises(SystemExit) as error:
        main(["analyze", "--input", str(source), "--output", str(output)])
    assert error.value.code == 2
    assert source.read_text() == ""


def test_sqlite_example_from_documentation(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples/sqlite_demo.py"
    process = subprocess.run(
        [sys.executable, str(script), "--directory", str(tmp_path / "demo")],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert "한국 시리즈 우승" in process.stdout
    assert (tmp_path / "demo/results.sqlite3").is_file()


def test_bundled_sample_integrity_and_demo():
    posts, metadata = load_sample()
    data = Path(__file__).resolve().parents[1] / "src/trending_keywords/data"
    assert len(posts) == metadata["sample_posts"] == 768
    assert (
        hashlib.sha256((data / "sample_posts.jsonl").read_bytes()).hexdigest() == metadata["sha256"]
    )
    assert all(set(p) == {"idx", "community", "title", "views", "reg_date"} for p in posts)
    assert all(
        p["idx"].startswith("sample_") and p["community"].startswith("community_") for p in posts
    )
    process = subprocess.run(
        [sys.executable, "-m", "trending_keywords", "demo", "--format", "json"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    report = json.loads(process.stdout)
    assert report["recent_posts"] == metadata["recent_posts"]
    assert report["background_posts"] == metadata["background_posts"]
    assert report["keywords"] and report["keywords"][0]["keyword"] == "한국 시리즈 우승"
    assert not process.stderr
