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
        assert log[0].startswith("2026-10-29|Tilbakestilling til gjeldende tekst")
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


def _source_repo(tmp_path, removed_refid="lov/2010-01-01-5", removal_date="2026-07-21T03:00:00+00:00"):
    """A publication repository whose main once carried a document that was later deleted."""
    src = tmp_path / "source"
    (src / "lover").mkdir(parents=True)
    _git(src, "init", "-q", "-b", "main")
    path = src / "lover" / (removed_refid.replace("/", "-") + ".md")
    path.write_text(f'---\ntittel: "Lov om gammelt"\nrefid: "{removed_refid}"\n---\n\n# Lov om gammelt\n\n### § 1\n\nGammel tekst.\n', encoding="utf-8")
    (src / "lover" / "lov-2020-01-01-1.md").write_text("current\n", encoding="utf-8")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "publish", date="2026-02-18T03:00:00+00:00")
    path.unlink()
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "Oppdater lover [skip ci]", date=removal_date)
    return src


class TestRemovedDocuments:
    def test_reads_terminal_text_and_detected_exit(self, tmp_path):
        from lovdata_publisher.git_export import removed_documents
        src = _source_repo(tmp_path)
        removed = removed_documents(str(src))
        assert list(removed) == ["lover/lov-2010-01-01-5.md"]
        info = removed["lover/lov-2010-01-01-5.md"]
        assert "Gammel tekst." in info["text"] and info["detected_exit"] == "2026-07-21"
        assert len(info["removal_commit"]) == 40
        assert removed_documents(str(src), cutoff_date="2026-07-01") == {}

    def test_repealed_document_stays_until_a_dated_deletion_commit(self, tmp_path):
        snap = _snapshot(tmp_path, [
            ("lov/2024-06-01-10", "2024-07-01", "2024-06-01", "§ 1. Formål\nTekst fra 2024."),
        ])
        with sqlite3.connect(snap / "amendments.db") as conn:
            conn.execute("INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("lov/2025-12-01-99", "y.xml", "Lov om oppheving", "", "2026-01-01", "2026-01-01", 0,
                          "2025-12-01", "Testdepartementet", "lov/2010-01-01-5", "", "", 1))
            conn.execute("INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) VALUES (?,?,?,?,?,?)",
                         ("lov/2025-12-01-99", "repeal", "", "lov/2010-01-01-5", "Lov 1. januar 2010 nr. 5 om gammelt oppheves.", ""))
        src = _source_repo(tmp_path)
        repo = tmp_path / "repo"
        build_history(str(snap), str(repo), mode="act", cutoff_date="2026-10-29", removed_source=str(src))
        log = _git(repo, "log", "--format=%ad|%s", "--date=short").splitlines()
        assert log[0].startswith("2026-10-29|Tilbakestilling til gjeldende tekst (")
        assert any(line.startswith("2026-01-01|Opphevet: Lov om gammelt") for line in log)
        assert log[-1].startswith("2001-01-01|Utgangspunkt: gjeldende tekst for 2 dokumenter")
        assert "Gammel tekst." in _git(repo, "show", "v2024:lover/lov-2010-01-01-5.md")
        assert "lov-2010-01-01-5" not in _git(repo, "ls-tree", "--name-only", "-r", "v2026")
        body = _git(repo, "log", "-1", "--format=%B", "v2026~1")
        assert "Rettslig opphevelse: lov/2025-12-01-99 i kraft 2026-01-01" in body
        assert "Registrert fjernet fra kilden: 2026-07-21" in body
        manifest = json.loads(_git(repo, "show", "HEAD:reconstruction-manifest.json"))
        assert manifest["counts"] == {"documents": 1, "diverged": 1, "removed": 1}
        assert manifest["documents"]["lov/2020-01-01-1"]["diverged"] is True
        assert manifest["documents"]["lov/2020-01-01-1"]["replayed_acts"] == 1
        removed = manifest["documents"]["lov/2010-01-01-5"]["removed"]
        assert removed["legal_repeal_date"] == "2026-01-01" and removed["deletion_date"] == "2026-01-01"
        assert removed["detected_exit"] == "2026-07-21"
        dates = [line.split("|")[0] for line in log]
        assert dates == sorted(dates, reverse=True)

    def test_new_format_repeal_record_with_refid_target_dates_the_deletion(self, tmp_path):
        from lovdata_publisher.git_export import legal_repeal
        snap = _snapshot(tmp_path, [("lov/2024-06-01-10", "2024-07-01", "2024-06-01", "§ 1. Formål\nTekst.")])
        with sqlite3.connect(snap / "amendments.db") as conn:
            conn.execute("INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("lov/2025-06-20-105", "y.xml", "Lov om Enhetsregisteret", "", "2026-01-01", "2026-01-01", 0,
                          "2025-06-20", "NFD", "lov/1994-06-03-15", "", "", 1))
            conn.execute("INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) VALUES (?,?,?,?,?,?)",
                         ("lov/2025-06-20-105", "repeal", "lov/1994-06-03-15", "lov/1994-06-03-15", "", ""))
            assert legal_repeal(conn, "lov/1994-06-03-15", "2026-10-30") == ("lov/2025-06-20-105", "2026-01-01")
            assert legal_repeal(conn, "lov/1994-06-03-15", "2025-12-31") == ("lov/2025-06-20-105", "")

    def test_deferred_repeal_takes_its_date_from_the_commencement_decision(self, tmp_path):
        """Real case: lov/2025-06-20-105 repeals the 1994 enhetsregisterloven but
        its in-force field says 'Kongen bestemmer'; forskrift/2025-06-20-1094
        ('Delt ikraftsetting av loven') sets it in force 2026-01-01. The loader's
        resolved date for the act is its publication date, which is wrong here."""
        from lovdata_publisher.git_export import legal_repeal
        snap = _snapshot(tmp_path, [("lov/2024-06-01-10", "2024-07-01", "2024-06-01", "§ 1. Formål\nTekst.")])
        with sqlite3.connect(snap / "amendments.db") as conn:
            conn.execute("INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("lov/2025-06-20-105", "y.xml", "Lov om Enhetsregisteret", "", "Kongen bestemmer", "2025-06-20", 1,
                          "2025-06-20", "NFD", "lov/1994-06-03-15", "", "", 1))
            conn.execute("INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) VALUES (?,?,?,?,?,?)",
                         ("lov/2025-06-20-105", "repeal", "lov/1994-06-03-15", "lov/1994-06-03-15", "", ""))
            assert legal_repeal(conn, "lov/1994-06-03-15", "2026-10-30") == ("lov/2025-06-20-105", "")
            conn.execute("INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("forskrift/2025-06-20-1094", "z.xml", "Delt ikraftsetting av lov 20. juni 2025 nr. 105", "",
                          "2026-01-01, Kongen bestemmer", "2025-06-20", 1, "2025-06-20", "NFD",
                          "lov/1994-06-03-15,lov/2025-06-20-105", "", "", 1))
            conn.execute("INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) VALUES (?,?,?,?,?,?)",
                         ("forskrift/2025-06-20-1094", "commencement", "", "lov/1994-06-03-15", "Delt ikraftsetting av loven.", "Loven trer i kraft 1. januar 2026."))
            assert legal_repeal(conn, "lov/1994-06-03-15", "2026-10-30") == ("lov/2025-06-20-105", "2026-01-01")

    def test_without_legal_repeal_the_deletion_is_dated_on_the_detected_exit(self, tmp_path):
        snap = _snapshot(tmp_path, [("lov/2024-06-01-10", "2024-07-01", "2024-06-01", "§ 1. Formål\nTekst.")])
        src = _source_repo(tmp_path)
        repo = tmp_path / "repo"
        build_history(str(snap), str(repo), mode="year", cutoff_date="2026-10-29", removed_source=str(src))
        log = _git(repo, "log", "--format=%ad|%s", "--date=short")
        assert "2026-07-21|Opphevet: Lov om gammelt" not in log  # year mode batches the deletion into the 2026 commit
        assert "lov-2010-01-01-5" in _git(repo, "ls-tree", "--name-only", "-r", "v2024")
        assert "lov-2010-01-01-5" not in _git(repo, "ls-tree", "--name-only", "-r", "v2026")
        manifest = json.loads(_git(repo, "show", "HEAD:reconstruction-manifest.json"))
        assert manifest["documents"]["lov/2010-01-01-5"]["removed"]["legal_repeal_act"] == ""
        assert manifest["documents"]["lov/2010-01-01-5"]["removed"]["deletion_date"] == "2026-07-21"
