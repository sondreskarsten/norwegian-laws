import importlib.util
import os
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def doc(refid, tittel, korttittel, dep, sist, body="Tekst."):
    return (f'---\ntittel: "{tittel}"\nkorttittel: "{korttittel}"\nrefid: "{refid}"\n'
            f'departement: "{dep}"\nsist-endret: "{sist}"\n---\n\n# {tittel}\n\n{body}\n')


def test_summary_lists_new_and_modified_documents_by_source(tmp_path, monkeypatch):
    repo = tmp_path
    (repo / "lover").mkdir()
    (repo / "forskrifter").mkdir()
    (repo / "lover/lov-2008-06-20-44.md").write_text(doc("lov/2008-06-20-44", "Lov om medisinsk forskning", "Helseforskningsloven", "HOD", "lov/2018-06-22-76"), encoding="utf-8")
    (repo / "lover/lov-2014-06-20-43.md").write_text(doc("lov/2014-06-20-43", "Lov om helseregistre", "Helseregisterloven", "HOD", "lov/2018-06-22-76"), encoding="utf-8")
    (repo / "lover/lov-1998-07-17-56.md").write_text(doc("lov/1998-07-17-56", "Lov om årsregnskap", "Regnskapsloven", "FIN", "lov/2024-06-21-41"), encoding="utf-8")
    (repo / "forskrifter/forskrift-2020-12-15-2912.md").write_text(doc("forskrift/2020-12-15-2912", "Integreringsforskriften", "", "AID", ""), encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    (repo / "lover/lov-2008-06-20-44.md").write_text(doc("lov/2008-06-20-44", "Lov om medisinsk forskning", "Helseforskningsloven", "HOD", "lov/2025-06-20-71", "Ny tekst."), encoding="utf-8")
    (repo / "lover/lov-2014-06-20-43.md").write_text(doc("lov/2014-06-20-43", "Lov om helseregistre", "Helseregisterloven", "HOD", "lov/2025-06-20-71", "Ny tekst."), encoding="utf-8")
    (repo / "lover/lov-1998-07-17-56.md").write_text(doc("lov/1998-07-17-56", "Lov om årsregnskap", "Regnskapsloven", "FIN", "lov/2024-06-21-41", "Omformatert."), encoding="utf-8")
    (repo / "forskrifter/forskrift-2026-10-30-2189.md").write_text(doc("forskrift/2026-10-30-2189", "Forskrift om endring i integreringsforskriften", "", "Arbeids- og inkluderingsdepartementet", "", "I forskrift ..."), encoding="utf-8")
    monkeypatch.chdir(repo)
    module = load("summarize_delta")
    new, modified = module.collect()
    assert [e["refid"] for e in new] == ["forskrift/2026-10-30-2189"]
    assert [e["refid"] for e in modified] == ["lov/2008-06-20-44", "lov/2014-06-20-43"]
    text = module.summarize(new, modified)
    lines = text.splitlines()
    assert lines[0] == "1 nytt dokument og 2 endrede dokumenter i denne publiseringen."
    assert "- forskrift/2026-10-30-2189: Forskrift om endring i integreringsforskriften (Arbeids- og inkluderingsdepartementet)" in lines
    assert ("- lov/2025-06-20-71 endrer 2 dokumenter: lov/2008-06-20-44 Helseforskningsloven; "
            "lov/2014-06-20-43 Helseregisterloven") in lines
    assert "lov/1998-07-17-56" not in text


def test_empty_delta_gives_empty_summary():
    module = load("summarize_delta")
    assert module.summarize([], []) == ""


def test_inject_summary_puts_entries_below_the_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# X\n\n<!-- AI_SUMMARY_START -->\n<!-- AI_SUMMARY_END -->\n\n<!-- RECENT_AMENDMENTS_START -->\n", encoding="utf-8")
    (tmp_path / "RELEASES.md").write_text("# Release notes\n\nIntro.\n\n<!-- ENTRIES -->\n## 2026-07-28\n\nold\n", encoding="utf-8")
    (tmp_path / "summary.md").write_text("2 endrede dokumenter i denne publiseringen.\n", encoding="utf-8")
    monkeypatch.setenv("SUMMARY_FILE", str(tmp_path / "summary.md"))
    monkeypatch.delenv("SUMMARY", raising=False)
    load("inject_summary").main()
    releases = (tmp_path / "RELEASES.md").read_text(encoding="utf-8")
    assert releases.index("Intro.") < releases.index("<!-- ENTRIES -->") < releases.index("2 endrede dokumenter") < releases.index("## 2026-07-28")
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "2 endrede dokumenter" in readme and "generert fra publiseringens diff" in readme
