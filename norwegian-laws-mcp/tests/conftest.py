import json
import subprocess
from pathlib import Path

import pytest

from norwegian_laws_mcp.repo import Repo
from norwegian_laws_mcp.service import LawsService

LAW = """---
tittel: "Lov om Enhetsregisteret (enhetsregisterloven)"
korttittel: "Enhetsregisterloven"
refid: "lov/2025-06-20-105"
eli: "/eli/lov/2025/06/20/105"
departement: "Nærings- og fiskeridepartementet"
ikrafttredelse: "2026-01-01"
---

# Lov om Enhetsregisteret (enhetsregisterloven)

## Kapittel 1. Innledende bestemmelser

#### § 1-1. Lovens formål

Formålet med loven er å legge til rette for effektiv bruk av grunndata.

#### § 1-4. Definisjoner

(1) Med registreringsenhet menes i denne loven enhet som har registreringsplikt.

## Kapittel 4. Hvilke opplysninger som skal registreres

#### § 4-7. Opplysninger om underenheter

(1) Næringsdrivende enheter skal registreres med én eller flere underenheter.

(2) Hver underenhet skal tildeles et eget organisasjonsnummer.

#### § 4-7 a. Særregel

Tekst om særregel.
"""

LAW_V2 = LAW.replace(
    "(2) Hver underenhet skal tildeles et eget organisasjonsnummer.",
    "(2) Hver underenhet skal tildeles et eget organisasjonsnummer av registerføreren.",
)

FORSKRIFT = """---
tittel: "Forskrift til lov om Enhetsregisteret (enhetsregisterforskriften)"
korttittel: "Enhetsregisterforskriften"
refid: "forskrift/2025-08-06-1610"
departement: "Nærings- og fiskeridepartementet"
ikrafttredelse: "2026-01-01"
---

# Forskrift til lov om Enhetsregisteret (enhetsregisterforskriften)

## Kapittel 4. Underenheter

#### § 4-1. Underenhet

Med underenhet menes opplysninger som skal registreres etter enhetsregisterloven § 4-7.
Lov 20. juni 2025 nr. 105 gjelder.
"""

AKSJELOVEN = """---
tittel: "Lov om aksjeselskaper (aksjeloven)"
korttittel: "Aksjeloven – asl"
refid: "lov/1997-06-13-44"
departement: "Nærings- og fiskeridepartementet"
---

# Lov om aksjeselskaper (aksjeloven)

## Kapittel 1. Innledende bestemmelser

### II. Definisjoner

##### § 1-5. Nærstående

Som noens nærstående menes ektefelle og slektninger.

##### § 1-5 a. Møte

Med møte menes også elektronisk møte.
"""

HISTORIE = """---
tittel: "Aksjeloven – asl"
refid: "lov/1997-06-13-44"
---

# Endringshistorikk: Aksjeloven – asl

## § 1-5

### 2013-06-14 — lov/2013-06-14-40

*§ 1-5 første ledd skal lyde:*

> Som noens nærstående menes ektefelle og slektninger.
>

### 2020-01-01 — lov/2019-12-20-100

*§ 1-5 annet ledd oppheves.*

## (annet)

### 2021-05-05 — lov/2021-05-05-50

*Overskriften til § 1-5 skal lyde:*

> § 1-5. Nærstående
"""


def catalog_json():
    return json.dumps([
        {
            "file": "lov-2025-06-20-105.md", "refid": "lov/2025-06-20-105", "eli": "/eli/lov/2025/06/20/105",
            "tittel": "Lov om Enhetsregisteret (enhetsregisterloven)", "korttittel": "Enhetsregisterloven",
            "aliases": [], "departement": ["Nærings- og fiskeridepartementet"], "kind": "lov",
            "path": "lover/lov-2025-06-20-105.md", "ikrafttredelse": "2026-01-01", "sist_endret": "",
            "github": "", "lovdata": "https://lovdata.no/dokument/NL/lov/2025-06-20-105", "log": "",
            "tags": [], "amendments": 0, "historie": None,
        },
        {
            "file": "forskrift-2025-08-06-1610.md", "refid": "forskrift/2025-08-06-1610",
            "tittel": "Forskrift til lov om Enhetsregisteret (enhetsregisterforskriften)",
            "korttittel": "Enhetsregisterforskriften", "aliases": [], "departement": ["Nærings- og fiskeridepartementet"],
            "kind": "forskrift", "path": "forskrifter/forskrift-2025-08-06-1610.md", "ikrafttredelse": "2026-01-01",
            "sist_endret": "", "github": "", "lovdata": "https://lovdata.no/dokument/SF/forskrift/2025-08-06-1610",
            "log": "", "tags": [], "amendments": 0, "historie": None,
        },
        {
            "file": "lov-1997-06-13-44.md", "refid": "lov/1997-06-13-44", "tittel": "Lov om aksjeselskaper (aksjeloven)",
            "korttittel": "Aksjeloven – asl", "aliases": ["asl", "aksjeloven"],
            "departement": ["Nærings- og fiskeridepartementet"], "kind": "lov", "path": "lover/lov-1997-06-13-44.md",
            "ikrafttredelse": "1999-01-01", "sist_endret": "lov/2025-06-20-106", "github": "",
            "lovdata": "https://lovdata.no/dokument/NL/lov/1997-06-13-44", "log": "", "tags": [],
            "amendments": 3, "historie": "historie/aksjeloven.html",
        },
        {
            "file": "forskrift-2026-01-01-1.md", "refid": "forskrift/2026-01-01-1",
            "tittel": "Forskrift om endring i enhetsregisterforskriften", "korttittel": "Endr. i enhetsregisterforskriften",
            "aliases": [], "departement": ["Nærings- og fiskeridepartementet"], "kind": "forskrift",
            "path": "forskrifter/forskrift-2026-01-01-1.md", "ikrafttredelse": "2026-02-01", "sist_endret": "",
            "github": "", "lovdata": "", "log": "", "tags": [], "amendments": 0, "historie": None,
        },
    ], ensure_ascii=False)


def git(path: Path, *args: str, date: str) -> None:
    env = {
        "GIT_AUTHOR_NAME": "Lovtidend", "GIT_AUTHOR_EMAIL": "l@example.org",
        "GIT_COMMITTER_NAME": "Lovtidend", "GIT_COMMITTER_EMAIL": "l@example.org",
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
        "HOME": str(path), "PATH": __import__("os").environ["PATH"],
    }
    subprocess.run(["git", *args], cwd=path, env=env, check=True, capture_output=True)


@pytest.fixture(scope="session")
def fixture_repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("laws")
    (root / "lover").mkdir()
    (root / "forskrifter").mkdir()
    (root / "historie").mkdir()
    git(root, "init", "-q", "-b", "main", date="2026-01-01T10:00:00+00:00")
    (root / "lover/lov-2025-06-20-105.md").write_text(LAW, encoding="utf-8")
    (root / "lover/lov-1997-06-13-44.md").write_text(AKSJELOVEN, encoding="utf-8")
    (root / "historie/aksjeloven.md").write_text(HISTORIE, encoding="utf-8")
    (root / "laws.json").write_text(catalog_json(), encoding="utf-8")
    git(root, "add", "-A", date="2026-01-01T10:00:00+00:00")
    git(root, "commit", "-q", "-m", "Initial import", date="2026-01-01T10:00:00+00:00")
    (root / "forskrifter/forskrift-2025-08-06-1610.md").write_text(FORSKRIFT, encoding="utf-8")
    git(root, "add", "-A", date="2026-02-01T10:00:00+00:00")
    git(root, "commit", "-q", "-m", "Oppdater lover og forskrifter fra Lovdata API 2026-02-01 [skip ci]",
        date="2026-02-01T10:00:00+00:00")
    (root / "lover/lov-2025-06-20-105.md").write_text(LAW_V2, encoding="utf-8")
    (root / "forskrifter/forskrift-2026-01-01-1.md").write_text(
        "---\ntittel: \"Forskrift om endring i enhetsregisterforskriften\"\nrefid: \"forskrift/2026-01-01-1\"\n---\n\n# Endring\n\nI\n", encoding="utf-8")
    git(root, "add", "-A", date="2026-03-01T10:00:00+00:00")
    git(root, "commit", "-q", "-m", "Oppdater lover og forskrifter fra Lovdata API 2026-03-01 [skip ci]",
        date="2026-03-01T10:00:00+00:00")
    return root


@pytest.fixture(scope="session")
def service(fixture_repo) -> LawsService:
    repo = Repo(fixture_repo, managed=False, update_on_start=False)
    repo.prepare_sync()
    return LawsService(repo)


@pytest.fixture
def anyio_backend():
    return "asyncio"
