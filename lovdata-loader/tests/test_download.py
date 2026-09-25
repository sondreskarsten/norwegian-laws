"""Source identity, cache integrity, and interruption regressions."""

import hashlib
import io
import json
from pathlib import Path
from urllib.parse import unquote

import pytest

from lovdata_loader import download


LAWS = "gjeldende-lover.tar.bz2"
REGULATIONS = "gjeldende-sentrale-forskrifter.tar.bz2"
HISTORICAL = "lovtidend-avd1-2001-2025.tar.bz2"
CURRENT = "lovtidend-avd1-2026.tar.bz2"


@pytest.fixture
def upstream(monkeypatch):
    class Upstream:
        bodies = {
            LAWS: b"laws-old",
            REGULATIONS: b"regs-old",
            HISTORICAL: b"historical",
            CURRENT: b"current",
        }
        entries = [
            {
                "filename": filename,
                "description": "Public archive",
                "lastModified": "2026-09-24T01:30:00Z",
                "sizeBytes": str(len(body)),
            }
            for filename, body in bodies.items()
        ]
        downloads = []
        failing = None
        manifest_reads = 0
        change_during_download = None

        def urlopen(self, url, **kwargs):
            assert url == "https://api.lovdata.no/v1/publicData/list"
            self.manifest_reads += 1
            return io.BytesIO(json.dumps(self.entries).encode())

        def urlretrieve(self, url, filename):
            assert url.startswith("https://api.lovdata.no/v1/publicData/get/")
            name = unquote(url.rsplit("/", 1)[-1])
            self.downloads.append(name)
            if name == self.failing:
                Path(filename).write_bytes(b"interrupted")
                raise OSError("connection interrupted")
            # Preserve an observable result for incorrectly invented archive names.
            Path(filename).write_bytes(self.bodies.get(name, b"unexpected"))
            if name == self.change_during_download:
                self.change(name, b"replaced")
            return str(filename), {}

        def change(self, name, body):
            self.bodies[name] = body
            for entry in self.entries:
                if entry["filename"] == name:
                    entry["lastModified"] = "2026-09-25T01:30:00Z"
                    entry["sizeBytes"] = str(len(body))

    server = Upstream()
    monkeypatch.setattr(download.urllib.request, "urlopen", server.urlopen)
    monkeypatch.setattr(download.urllib.request, "urlretrieve", server.urlretrieve)
    return server


def test_standalone_existing_path_does_not_claim_source_freshness(tmp_path, upstream):
    dest = tmp_path / LAWS
    dest.write_bytes(b"stale")
    returned = download.download_file(f"{download.BASE_URL}/{LAWS}", str(dest))
    assert returned == str(dest)
    assert dest.read_bytes() == b"laws-old"


def test_interrupted_initial_download_leaves_no_cache_entry(tmp_path, upstream):
    upstream.failing = LAWS
    dest = tmp_path / LAWS
    with pytest.raises(OSError, match="interrupted"):
        download.download_file(f"{download.BASE_URL}/{LAWS}", str(dest))
    assert list(tmp_path.iterdir()) == []


def test_interrupted_replacement_preserves_previous_archive(tmp_path, upstream):
    upstream.failing = LAWS
    dest = tmp_path / LAWS
    dest.write_bytes(b"previous-good")
    with pytest.raises(OSError, match="interrupted"):
        download.download_file(f"{download.BASE_URL}/{LAWS}", str(dest))
    assert dest.read_bytes() == b"previous-good"
    assert list(tmp_path.iterdir()) == [dest]


def test_same_filename_and_size_with_changed_manifest_is_refetched(tmp_path, upstream):
    download.download_archives(str(tmp_path))
    upstream.change(LAWS, b"laws-new")
    download.download_archives(str(tmp_path))
    assert (tmp_path / LAWS).read_bytes() == b"laws-new"
    assert upstream.downloads.count(LAWS) == 2
    assert upstream.downloads.count(REGULATIONS) == 1


def test_unchanged_verified_archives_reuse_cache(tmp_path, upstream):
    download.download_archives(str(tmp_path))
    download.download_archives(str(tmp_path))
    assert sorted(upstream.downloads) == sorted([LAWS, REGULATIONS, HISTORICAL, CURRENT])
    assert upstream.manifest_reads == 4
    assert (tmp_path / LAWS).read_bytes() == b"laws-old"
    metadata = json.loads((tmp_path / (LAWS + ".download.json")).read_text())
    assert metadata["sha256"] == hashlib.sha256(b"laws-old").hexdigest()
    assert metadata["source"] == {
        "filename": LAWS, "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 8,
    }


def test_same_size_local_corruption_is_refetched(tmp_path, upstream):
    download.download_archives(str(tmp_path))
    (tmp_path / LAWS).write_bytes(b"tampered")
    download.download_archives(str(tmp_path))
    assert (tmp_path / LAWS).read_bytes() == b"laws-old"
    assert upstream.downloads.count(LAWS) == 2
    assert upstream.downloads.count(REGULATIONS) == 1


@pytest.mark.parametrize("metadata", [None, "broken json"])
def test_missing_or_corrupt_sidecar_cannot_validate_cache(tmp_path, upstream, metadata):
    download.download_archives(str(tmp_path))
    sidecar = tmp_path / (LAWS + ".download.json")
    if metadata is None:
        sidecar.unlink(missing_ok=True)
    else:
        sidecar.write_text(metadata)
    download.download_archives(str(tmp_path))
    assert upstream.downloads.count(LAWS) == 2
    assert (tmp_path / LAWS).read_bytes() == b"laws-old"


def test_legacy_archives_without_identity_are_replaced(tmp_path, upstream):
    for name in upstream.bodies:
        (tmp_path / name).write_bytes(b"legacy")
    download.download_archives(str(tmp_path))
    assert (tmp_path / LAWS).read_bytes() == b"laws-old"
    assert (tmp_path / REGULATIONS).read_bytes() == b"regs-old"
    assert sorted(upstream.downloads) == sorted(upstream.bodies)


def test_archive_selection_follows_new_available_year(tmp_path, upstream):
    upstream.entries = [entry for entry in upstream.entries if entry["filename"] != CURRENT]
    upstream.entries.append({
        "filename": "lovtidend-avd1-2027.tar.bz2", "description": "Next year",
        "lastModified": "2027-01-02T01:30:00Z", "sizeBytes": "4",
    })
    upstream.bodies["lovtidend-avd1-2027.tar.bz2"] = b"next"
    paths = download.download_archives(str(tmp_path))
    assert paths["gjeldende"] == str(tmp_path / LAWS)
    assert paths["forskrifter"] == str(tmp_path / REGULATIONS)
    assert paths["lovtidend"] == [
        str(tmp_path / HISTORICAL), str(tmp_path / "lovtidend-avd1-2027.tar.bz2"),
    ]
    assert CURRENT not in upstream.downloads
    assert (tmp_path / "lovtidend-avd1-2027.tar.bz2").read_bytes() == b"next"


def test_receipt_is_canonical_selected_manifest(tmp_path, upstream):
    upstream.entries.append({
        "filename": "unrelated.tar.bz2", "lastModified": "later", "sizeBytes": "999",
    })
    download.download_archives(str(tmp_path))
    receipt = json.loads((tmp_path / "source-manifest.json").read_text())
    assert receipt == [
        {"filename": LAWS, "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 8},
        {"filename": REGULATIONS, "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 8},
        {"filename": HISTORICAL, "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 10},
        {"filename": CURRENT, "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 7},
    ]
    assert "unrelated.tar.bz2" not in upstream.downloads


def test_failed_multi_archive_refresh_invalidates_previous_receipt(tmp_path, upstream):
    download.download_archives(str(tmp_path))
    receipt = tmp_path / "source-manifest.json"
    # Also models an earlier deployed receipt when run against the legacy downloader.
    receipt.write_text(json.dumps(upstream.entries))
    upstream.change(LAWS, b"laws-new")
    upstream.change(REGULATIONS, b"regs-new")
    upstream.failing = REGULATIONS
    with pytest.raises(OSError, match="interrupted"):
        download.download_archives(str(tmp_path))
    assert (tmp_path / LAWS).read_bytes() == b"laws-new"
    assert (tmp_path / REGULATIONS).read_bytes() == b"regs-old"
    assert not receipt.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_wrong_download_size_is_not_committed(tmp_path, upstream):
    upstream.bodies[LAWS] = b"truncated"
    with pytest.raises(ValueError, match="size"):
        download.download_archives(str(tmp_path))
    assert not (tmp_path / LAWS).exists()
    assert not (tmp_path / (LAWS + ".download.json")).exists()
    assert not (tmp_path / "source-manifest.json").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_truncated_refresh_preserves_previous_archive_and_digest(tmp_path, upstream):
    download.download_archives(str(tmp_path))
    sidecar = tmp_path / (LAWS + ".download.json")
    previous_digest = json.loads(sidecar.read_text())["sha256"]
    upstream.change(LAWS, b"laws-new")
    upstream.bodies[LAWS] = b"short"
    with pytest.raises(ValueError, match="size"):
        download.download_archives(str(tmp_path))
    assert (tmp_path / LAWS).read_bytes() == b"laws-old"
    assert json.loads(sidecar.read_text())["sha256"] == previous_digest
    assert not (tmp_path / "source-manifest.json").exists()


def test_manifest_changing_during_transfer_cannot_produce_receipt(tmp_path, upstream):
    upstream.change_during_download = LAWS
    with pytest.raises(ValueError, match="manifest changed"):
        download.download_archives(str(tmp_path))
    assert not (tmp_path / "source-manifest.json").exists()


def test_selection_normalizes_manifest_for_polling(upstream):
    upstream.entries.reverse()
    selected = download.select_source_manifest(upstream.entries)
    assert [entry["filename"] for entry in selected] == [LAWS, REGULATIONS, HISTORICAL, CURRENT]
    assert [entry["sizeBytes"] for entry in selected] == [8, 8, 10, 7]
    assert all(set(entry) == {"filename", "lastModified", "sizeBytes"} for entry in selected)
    assert download.select_source_manifest(selected) == selected


@pytest.mark.parametrize("invalid", ["missing-laws", "missing-lovtidend", "duplicate", "unsafe-name", "bad-size", "bool-size", "fractional-size"])
def test_invalid_selected_manifest_fails_before_download(tmp_path, upstream, invalid):
    if invalid == "missing-laws":
        upstream.entries = [entry for entry in upstream.entries if entry["filename"] != LAWS]
    elif invalid == "missing-lovtidend":
        upstream.entries = [entry for entry in upstream.entries if not entry["filename"].startswith("lovtidend-")]
    elif invalid == "duplicate":
        upstream.entries.append(dict(upstream.entries[0]))
    elif invalid == "unsafe-name":
        upstream.entries.append({"filename": "lovtidend-avd1-../escape.tar.bz2", "sizeBytes": 4, "lastModified": "now"})
    elif invalid == "bool-size":
        upstream.entries[0]["sizeBytes"] = True
    elif invalid == "fractional-size":
        upstream.entries[0]["sizeBytes"] = 8.5
    else:
        upstream.entries[0]["sizeBytes"] = "not-a-number"
    with pytest.raises(ValueError):
        download.download_archives(str(tmp_path))
    assert not upstream.downloads
    assert not (tmp_path / "source-manifest.json").exists()
