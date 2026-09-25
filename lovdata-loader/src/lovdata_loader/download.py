"""Download and verify the public archives selected by Lovdata's live manifest."""
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

BASE_URL = "https://api.lovdata.no/v1/publicData/get"
LIST_URL = "https://api.lovdata.no/v1/publicData/list"

ARCHIVES = {
    "gjeldende": "gjeldende-lover.tar.bz2",
    "forskrifter": "gjeldende-sentrale-forskrifter.tar.bz2",
}


def _source_entry(entry: dict) -> dict:
    """Validate the source identity without lossy size coercion."""
    filename = entry.get("filename")
    modified = entry.get("lastModified")
    size = entry.get("sizeBytes")
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise ValueError(f"Invalid archive filename: {filename!r}")
    if not isinstance(modified, str) or not modified.strip():
        raise ValueError(f"Missing lastModified for {filename}")
    if isinstance(size, str) and re.fullmatch(r"[0-9]+", size):
        size = int(size)
    if type(size) is not int or size <= 0:
        raise ValueError(f"Invalid sizeBytes for {filename}: {size!r}")
    return {"filename": filename, "lastModified": modified, "sizeBytes": size}


def select_source_manifest(payload: list[dict]) -> list[dict]:
    """Return the canonical archive identities used by downloading and polling.

    Accepts the public ``/list`` JSON or an earlier receipt. Selects both
    consolidated archives and every available ``lovtidend-avd1-*.tar.bz2``;
    unrelated files are ignored. The result is sorted by filename, contains
    only filename/lastModified/sizeBytes, and normalizes sizeBytes to integers.
    """
    if not isinstance(payload, list):
        raise ValueError("Lovdata manifest must be a list")
    selected = {}
    for entry in payload:
        if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
            raise ValueError("Lovdata manifest entry must contain a filename")
        filename = entry["filename"]
        if filename not in ARCHIVES.values() and not (
            filename.startswith("lovtidend-avd1-") and filename.endswith(".tar.bz2")
        ):
            continue
        identity = _source_entry(entry)
        if filename in selected:
            raise ValueError(f"Duplicate archive in Lovdata manifest: {filename}")
        selected[filename] = identity

    missing = set(ARCHIVES.values()) - selected.keys()
    if missing:
        raise ValueError(f"Lovdata manifest is missing archives: {', '.join(sorted(missing))}")
    if not any(name.startswith("lovtidend-avd1-") for name in selected):
        raise ValueError("Lovdata manifest contains no Lovtidend archives")
    return [selected[name] for name in sorted(selected)]


def fetch_source_manifest() -> list[dict]:
    """Fetch and select the live public manifest; failures never use old state."""
    with urllib.request.urlopen(LIST_URL, timeout=60) as response:
        return select_source_manifest(json.load(response))


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _atomic_json(path: Path, payload) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=".lovdata-", suffix=".tmp", delete=False,
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _verified_cache(path: Path, sidecar: Path, url: str, source: dict) -> bool:
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        return (
            isinstance(metadata, dict)
            and metadata.get("url") == url
            and metadata.get("source") == source
            and metadata.get("sizeBytes") == source["sizeBytes"]
            and path.stat().st_size == source["sizeBytes"]
            and metadata.get("sha256") == _sha256(path)
        )
    except (OSError, ValueError, TypeError):
        return False


def download_file(url: str, dest: str, *, source: dict | None = None) -> str:
    """Download atomically, or reuse bytes verified against a source identity.

    Two-argument callers remain supported and always download: an existing
    filename alone cannot establish freshness. Manifest-aware callers supply
    filename/lastModified/sizeBytes and get size plus SHA256 cache validation.
    """
    path = Path(dest)
    sidecar = Path(f"{dest}.download.json")
    if source is not None:
        source = _source_entry(source)
    if source is not None and _verified_cache(path, sidecar, url, source):
        print(f"  Verified {dest} (source unchanged, SHA256 matches)")
        return dest

    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {url}...")
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".lovdata-", suffix=".tmp", delete=False,
    ) as stream:
        temporary = Path(stream.name)
    try:
        urllib.request.urlretrieve(url, temporary)
        size = temporary.stat().st_size
        if source is not None and size != source["sizeBytes"]:
            raise ValueError(
                f"Archive size mismatch for {path.name}: "
                f"expected {source['sizeBytes']}, downloaded {size}"
            )
        # Hash these exact downloaded bytes before replacing the shared path.
        digest = _sha256(temporary)
        os.replace(temporary, path)
        if source is not None:
            _atomic_json(sidecar, {
                "url": url, "source": source, "sizeBytes": size, "sha256": digest,
            })
        else:
            sidecar.unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"  Saved {dest} ({size / (1024 * 1024):.1f} MB)")
    return dest


def download_archives(output_dir: str = ".") -> dict[str, str | list[str]]:
    """Download selected archives and record their source manifest receipt.

    Returns gjeldende/forskrifter paths and a list of lovtidend paths, preserving
    the CLI contract. A directory must have a single writer. The receipt is
    invalidated before work starts and written only when every archive verifies
    and the selected upstream manifest is still unchanged after downloading.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / "source-manifest.json"
    receipt.unlink(missing_ok=True)
    manifest = fetch_source_manifest()
    paths = {}
    for source in manifest:
        filename = source["filename"]
        path = os.path.join(output_dir, filename)
        download_file(f"{BASE_URL}/{quote(filename, safe='')}", path, source=source)
        paths[filename] = path
    if fetch_source_manifest() != manifest:
        raise ValueError("Lovdata manifest changed during download; retry the download")
    _atomic_json(receipt, manifest)
    result = {key: paths[filename] for key, filename in ARCHIVES.items()}
    result["lovtidend"] = [path for name, path in paths.items() if name.startswith("lovtidend-avd1-")]
    return result
