"""Tests for lovdata_publisher.git_export."""
from lovdata_publisher.git_export import date_to_git_timestamp


# ─── date_to_git_timestamp ─────────────────────────────────────────────────

class TestDateToGitTimestamp:
    def test_valid_date(self):
        ts = date_to_git_timestamp("2024-01-01")
        assert "+0100" in ts
        assert ts.startswith("1704")

    def test_invalid_date(self):
        ts = date_to_git_timestamp("not-a-date")
        assert "+0100" in ts


# ─── create_yearly_tags / build_history ──────────────────────────────────────

import json
import sqlite3
import subprocess

from lovdata_publisher.git_export import build_history, create_yearly_tags


def _git(repo, *args, date=None):
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org",
        "HOME": str(repo), "PATH": __import__("os").environ["PATH"],
    }
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout


class TestCreateYearlyTags:
    def test_skips_years_after_max_year(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        for date in ("2025-03-01T12:00:00+00:00", "2026-06-01T12:00:00+00:00", "2027-01-01T12:00:00+00:00"):
            (repo / "f.txt").write_text(date)
            _git(repo, "add", "f.txt")
            _git(repo, "commit", "-q", "-m", date, date=date)
        tags = create_yearly_tags(str(repo), max_year=2026)
        assert sorted(tags) == ["v2025", "v2026"]
        assert "v2027" not in _git(repo, "tag")


def _snapshot(tmp_path, acts):
    snap = tmp_path / "snapshot"
    (snap / "laws").mkdir(parents=True)
    (snap / "forskrifter").mkdir()
    law = {
        "refid": "lov/2020-01-01-1", "title": "Lov om test", "short_title": "Testloven",
        "ministry": "Testdepartementet", "date_in_force": "2020-01-01", "last_amended_by": "",
        "sections": [{"header_text": "Kapittel 1", "articles": [
            {"name": "§1", "header_text": "§ 1. Formål", "paragraphs": [{"text": "Gjeldende tekst."}], "trailing_text": ""},
        ]}],
    }
    (snap / "laws" / "lov-2020-01-01-1.json").write_text(json.dumps(law), encoding="utf-8")
    with sqlite3.connect(snap / "amendments.db") as conn:
        conn.executescript("""
            CREATE TABLE amendment_acts (refid TEXT PRIMARY KEY, filename TEXT,
              title TEXT, short_title TEXT, date_in_force TEXT, date_in_force_resolved TEXT,
              is_deferred INTEGER, date_published TEXT, ministry TEXT, changes_to TEXT,
              misc_info TEXT, journal_number TEXT, amendment_count INTEGER);
            CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT,
              change_type TEXT, target TEXT, target_law TEXT, instruction TEXT, new_text TEXT);
        """)
        for refid, in_force, published, text in acts:
            conn.execute(
                "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (refid, "x.xml", f"Endringslov {refid}", "", in_force, in_force, 0, published,
                 "Testdepartementet", "lov/2020-01-01-1", "", "", 1))
            conn.execute(
                "INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) VALUES (?,?,?,?,?,?)",
                (refid, "change", "lov/2020-01-01-1/§1", "lov/2020-01-01-1", "§ 1 skal lyde:", text))
    return snap


class TestBuildHistoryCutoff:
    def test_future_acts_excluded_and_reset_dated_on_cutoff(self, tmp_path):
        snap = _snapshot(tmp_path, [
            ("lov/2024-06-01-10", "2024-07-01", "2024-06-01", "§ 1. Formål\nTekst fra 2024."),
            ("lov/2026-05-01-20", "2026-06-01", "2026-05-01", "§ 1. Formål\nTekst fra 2026."),
            ("lov/2026-09-01-30", "2027-01-01", "2026-09-01", "§ 1. Formål\nTekst fra 2027."),
        ])
        repo = tmp_path / "repo"
        build_history(str(snap), str(repo), mode="act", cutoff_date="2026-10-29")
        log = _git(repo, "log", "--format=%ad|%s", "--date=short").splitlines()
        assert log[0].startswith("2026-10-29|Gjeldende konsolidert tekst")
        assert not any("2027" in line.split("|")[0] for line in log)
        bodies = _git(repo, "log", "--format=%B")
        assert "lov/2026-05-01-20" in bodies
        assert "lov/2026-09-01-30" not in bodies
        assert "Tekst fra 2026." in _git(repo, "show", "v2026~1:lover/lov-2020-01-01-1.md")
        assert "Gjeldende tekst." in _git(repo, "show", "HEAD:lover/lov-2020-01-01-1.md")
        tags = _git(repo, "tag").split()
        assert tags == ["v2001", "v2024", "v2026"]
        dates = [line.split("|")[0] for line in log]
        assert dates == sorted(dates, reverse=True)
