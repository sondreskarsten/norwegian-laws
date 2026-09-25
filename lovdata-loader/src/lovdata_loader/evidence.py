"""Retain raw archive observations and export every parsed amendment occurrence.

The JSONL export is lossless relative to AmendmentActData, not relative to XML.
Raw archives and their member identities are retained separately for replay.
Neither publication dates nor source lastModified establish legal valid time.
"""
from __future__ import annotations

from dataclasses import asdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import tarfile

from . import __version__
from .parser import parse_law, parse_lovtidend_file
from .models import Amendment, AmendmentActData


OBSERVATIONS = "source-observations.json"
MEMBERS = "source-members.jsonl"
PARSED_ACTS = "parsed-amendment-acts.v1.jsonl"
EVIDENCE_VERSION = "lovdata-source-evidence-v1"
PARSED_ACT_VERSION = "parsed-amendment-acts-v1"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def value_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parser_identity() -> dict:
    source = Path(__file__).parent
    files = {name: file_sha256(source / name) for name in ("parser.py", "models.py", "evidence.py")}
    return {"package_version": __version__, "source_files": files, "sha256": value_sha256(files)}


def parser_runtime() -> dict:
    dependencies = {}
    for name in ("beautifulsoup4", "soupsieve", "lxml"):
        try:
            dependencies[name] = package_version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return {"python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(), "html_backend": "html.parser",
            "dependencies": dependencies, "unknown_dependency_version": None}


def _member_identity(member, ordinal: int, content: bytes | None) -> dict:
    return {"member_ordinal": ordinal, "member_path": member.name,
            "member_type": "file" if member.isfile() else "directory" if member.isdir() else "other",
            "member_size_bytes": member.size,
            "member_sha256": hashlib.sha256(content).hexdigest() if content is not None else None}


class EvidenceBundle:
    """A single input observation; CLI parsing and snapshot promotion share it."""

    def __init__(self):
        self.archives = []
        self.members = []
        self.records = {"laws": [], "forskrifter": [], "amendment_acts": []}
        self._paths = []
        self._sources = {kind: [] for kind in self.records}

    def parse_archive(self, archive_path: str, kind: str, *, prefixes=("nl-", "sf-")) -> list:
        if kind not in self.records:
            raise ValueError(f"Unsupported archive role: {kind}")
        path = Path(archive_path)
        digest = file_sha256(path)
        ordinal = len(self.archives)
        observation = {
            "archive_ordinal": ordinal, "archive_sha256": digest,
            "size_bytes": path.stat().st_size, "raw_path": f"raw/{digest}.tar.bz2",
            "original_filename": path.name, "role": kind,
            "prefixes": list(prefixes) if kind == "amendment_acts" else [],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "retrieved_at": None, "source_url": None, "source_last_modified": None,
            "retrieval_time_status": "unknown", "historical_knowledge_time_status": "unknown",
        }
        sidecar = Path(str(path) + ".download.json")
        if sidecar.is_file():
            receipt = json.loads(sidecar.read_text(encoding="utf-8"))
            if receipt.get("sha256") != digest or receipt.get("sizeBytes") != observation["size_bytes"]:
                raise ValueError(f"Download receipt does not match archive bytes: {path.name}")
            observation.update(source_url=receipt.get("url"), retrieved_at=receipt.get("retrieved_at"),
                               source_last_modified=(receipt.get("source") or {}).get("lastModified"))
            if observation["retrieved_at"]:
                observation["retrieval_time_status"] = "recorded"
        parsed = []
        with tarfile.open(path, "r:bz2") as archive:
            for member_ordinal, member in enumerate(archive.getmembers()):
                content = None
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        content = stream.read()
                row = {"archive_ordinal": ordinal, "archive_sha256": digest,
                       **_member_identity(member, member_ordinal, content),
                       "role": kind, "parse_status": "excluded_non_xml", "refid": None,
                       "parsed_occurrence_ordinal": None, "parsed_model_sha256": None,
                       "source_occurrence_id": None, "selected": False,
                       "selected_output_path": None, "selected_output_sha256": None}
                self.members.append(row)
                if not member.name.endswith(".xml"):
                    continue
                if not member.isfile():
                    raise ValueError(f"XML source member is not a regular file: {member.name}")
                if kind == "amendment_acts" and not Path(member.name).name.startswith(prefixes):
                    row["parse_status"] = "excluded_prefix"
                    continue
                record = (parse_lovtidend_file(content, Path(member.name).name)
                          if kind == "amendment_acts" else parse_law(content))
                if record is None:
                    row["parse_status"] = "unresolved_missing_refid"
                    continue
                row.update(parse_status="parsed", refid=record.refid,
                           parsed_model_sha256=value_sha256(asdict(record)))
                # Original tar position disambiguates repeated paths and language variants.
                row["source_occurrence_id"] = value_sha256(
                    [ordinal, digest, member_ordinal, member.name, row["member_sha256"], kind])
                parsed.append((record, row))
                if len(parsed) % 500 == 0:
                    print(f"  Parsed {len(parsed)} {kind} from {path.name}...")
        if file_sha256(path) != digest:
            raise ValueError(f"Archive changed while parsing: {path.name}")
        if kind == "amendment_acts":
            # Preserve the former CLI's nl-then-sf insertion order within each archive.
            parsed.sort(key=lambda pair: next(i for i, prefix in enumerate(prefixes)
                                             if Path(pair[1]["member_path"]).name.startswith(prefix)))
        for record, row in parsed:
            row["parsed_occurrence_ordinal"] = len(self.records[kind])
            self.records[kind].append(record)
            self._sources[kind].append(row)
        observation["member_count"] = sum(row["archive_ordinal"] == ordinal for row in self.members)
        observation["parsed_occurrence_count"] = len(parsed)
        self.archives.append(observation)
        self._paths.append(path)
        return [record for record, _ in parsed]

    def write(self, stage: Path, supplied_records: dict, output_hashes: dict) -> tuple[list[Path], dict]:
        """Write evidence before promotion and bind every selected materialization."""
        for kind, records in supplied_records.items():
            if len(records) != len(self.records[kind]):
                raise ValueError(f"Evidence {kind} count does not match parsed input")
            last = {record.refid: i for i, record in enumerate(records)}
            for i, (record, source) in enumerate(zip(records, self._sources[kind])):
                if value_sha256(asdict(record)) != source["parsed_model_sha256"]:
                    raise ValueError(f"Parsed {kind} changed after source capture: {record.refid}")
                source["selected"] = i == last[record.refid]
                if source["selected"]:
                    target = ("amendments.db" if kind == "amendment_acts" else
                              f"{kind}/{record.refid.replace('/', '-')}.json")
                    source["selected_output_path"] = target
                    source["selected_output_sha256"] = output_hashes[target]
        artifacts = []
        for source, path in zip(self.archives, self._paths):
            target = stage / source["raw_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                # Copy, not hard-link: a later local source edit must not change retained evidence.
                shutil.copyfile(path, target)
                artifacts.append(target)
            if target.stat().st_size != source["size_bytes"] or file_sha256(target) != source["archive_sha256"]:
                raise ValueError(f"Retained raw archive does not match parsed input: {path.name}")
        observations = {"schema_version": EVIDENCE_VERSION, "parser_identity": parser_identity(),
                        "parser_runtime": parser_runtime(),
                        "knowledge_cutoff": max((source["observed_at"] for source in self.archives), default=None),
                        "knowledge_cutoff_basis": "local_archive_observation",
                        "historical_knowledge_time_status": "unknown",
                        "source_attribution": "Lovdata public data; NLOD 2.0",
                        "structural_coverage_status": "not_verified",
                        "archives": self.archives}
        (stage / OBSERVATIONS).write_text(canonical_json(observations) + "\n", encoding="utf-8", newline="\n")
        with (stage / MEMBERS).open("w", encoding="utf-8", newline="\n") as stream:
            for row in self.members:
                stream.write(canonical_json(row) + "\n")
        with (stage / PARSED_ACTS).open("w", encoding="utf-8", newline="\n") as stream:
            for act, source in zip(self.records["amendment_acts"], self._sources["amendment_acts"]):
                row = {"schema_version": PARSED_ACT_VERSION,
                       "source_occurrence_id": source["source_occurrence_id"],
                       "parsed_occurrence_ordinal": source["parsed_occurrence_ordinal"],
                       "record": asdict(act),
                       "amendment_occurrences": [
                           {"ordinal": i, "target_status": "identified" if amendment.target_law else "unresolved",
                            "operation_status": "unresolved" if amendment.change_type == "unknown" else "identified"}
                           for i, amendment in enumerate(act.amendments)],
                       "legal_valid_time": {"status": "unresolved", "date": None},
                       "fidelity": "lossless_relative_to_parsed_model",
                       "source_structure_status": "not_verified"}
                stream.write(canonical_json(row) + "\n")
        artifacts.extend(stage / name for name in (OBSERVATIONS, MEMBERS, PARSED_ACTS))
        counts = {kind: len(records) for kind, records in self.records.items()}
        return artifacts, {"version": EVIDENCE_VERSION, "observations": OBSERVATIONS,
                           "members": MEMBERS, "parsed_amendments": PARSED_ACTS,
                           "archive_count": len(self.archives), "member_count": len(self.members),
                           "parsed_occurrence_counts": counts,
                           "parsed_amendment_count": sum(len(act.amendments) for act in self.records["amendment_acts"]),
                           "unresolved_member_count": sum(row["parse_status"].startswith("unresolved_")
                                                          for row in self.members)}


def _require(condition, message):
    if not condition:
        raise ValueError(f"Invalid source evidence: {message}")


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _count(value):
    return type(value) is int and value >= 0


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid source evidence JSON: {path.name}") from exc


def _jsonl(path):
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                _require(isinstance(row, dict), f"{path.name} row must be an object")
                yield row
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid source evidence JSONL: {path.name}: {exc}") from exc


def _timestamp(value):
    try:
        return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def evidence_artifacts(root: Path, manifest: dict) -> list[Path]:
    """Resolve only the supported v4 evidence paths; never accept arbitrary paths."""
    contract = manifest.get("evidence")
    _require(isinstance(contract, dict) and contract.get("version") == EVIDENCE_VERSION,
             "unsupported evidence contract")
    for key, name in (("observations", OBSERVATIONS), ("members", MEMBERS), ("parsed_amendments", PARSED_ACTS)):
        _require(contract.get(key) == name, f"unsupported {key} artifact")
        _require((root / name).is_file() and not (root / name).is_symlink(), f"missing/invalid {key} file")
    for key in ("archive_count", "member_count", "parsed_amendment_count", "unresolved_member_count"):
        _require(_count(contract.get(key)), key)
    counts = contract.get("parsed_occurrence_counts")
    _require(isinstance(counts, dict) and set(counts) == {"laws", "forskrifter", "amendment_acts"}
             and all(_count(value) for value in counts.values()), "parsed occurrence counts")
    observations = _read_json(root / OBSERVATIONS)
    _require(isinstance(observations, dict) and observations.get("schema_version") == EVIDENCE_VERSION,
             "unsupported observation schema")
    parser = observations.get("parser_identity")
    _require(isinstance(parser, dict) and isinstance(parser.get("package_version"), str), "parser identity")
    files = parser.get("source_files")
    _require(isinstance(files, dict) and set(files) == {"parser.py", "models.py", "evidence.py"}
             and all(_digest(value) for value in files.values()) and parser.get("sha256") == value_sha256(files),
             "parser source fingerprint")
    runtime = observations.get("parser_runtime")
    _require(isinstance(runtime, dict) and runtime.get("html_backend") == "html.parser"
             and all(isinstance(runtime.get(key), str) and runtime[key]
                     for key in ("python_implementation", "python_version")), "parser runtime")
    dependencies = runtime.get("dependencies")
    _require(isinstance(dependencies, dict) and set(dependencies) == {"beautifulsoup4", "soupsieve", "lxml"}
             and all(value is None or isinstance(value, str) and bool(value) for value in dependencies.values())
             and "unknown_dependency_version" in runtime and runtime["unknown_dependency_version"] is None,
             "parser dependency identity")
    _require(observations.get("knowledge_cutoff_basis") == "local_archive_observation"
             and observations.get("historical_knowledge_time_status") == "unknown"
             and observations.get("structural_coverage_status") == "not_verified", "observation time/coverage semantics")
    archives = observations.get("archives")
    _require(isinstance(archives, list) and len(archives) == contract["archive_count"], "archive count")
    paths = set()
    for ordinal, archive in enumerate(archives):
        _require(isinstance(archive, dict) and archive.get("archive_ordinal") == ordinal, "archive ordinal")
        digest = archive.get("archive_sha256")
        _require(_digest(digest) and archive.get("raw_path") == f"raw/{digest}.tar.bz2", "raw archive identity")
        _require(_count(archive.get("size_bytes")) and archive["size_bytes"] > 0, "archive size")
        _require(archive.get("role") in counts and _count(archive.get("member_count"))
                 and _count(archive.get("parsed_occurrence_count")), "archive role/count")
        prefixes = archive.get("prefixes")
        _require(isinstance(prefixes, list) and (prefixes == [] if archive["role"] != "amendment_acts"
                 else bool(prefixes) and len(set(prefixes)) == len(prefixes)
                 and all(prefix in ("nl-", "sf-") for prefix in prefixes)), "archive prefix scope")
        _require(isinstance(archive.get("original_filename"), str) and archive["original_filename"], "archive filename")
        _require(_timestamp(archive.get("observed_at")), "local observation time")
        retrieved = archive.get("retrieved_at")
        _require((retrieved is None and archive.get("retrieval_time_status") == "unknown")
                 or (_timestamp(retrieved) and archive.get("retrieval_time_status") == "recorded"), "retrieval time")
        _require(archive.get("historical_knowledge_time_status") == "unknown", "historical knowledge time")
        for field in ("source_url", "source_last_modified"):
            _require(archive.get(field) is None or isinstance(archive[field], str), field)
        path = root / archive["raw_path"]
        _require(path.is_file() and not path.is_symlink() and path.stat().st_size == archive["size_bytes"], "retained archive size/file")
        _require(manifest.get("artifact_hashes", {}).get(archive["raw_path"]) == digest, "archive hash binding")
        paths.add(archive["raw_path"])
    cutoff = max((archive["observed_at"] for archive in archives), default=None)
    _require(observations.get("knowledge_cutoff") == cutoff, "local observation cutoff")
    raw = root / "raw"
    _require(not raw.is_symlink() and not getattr(raw, "is_junction", lambda: False)(), "raw directory link")
    actual = {path.relative_to(root).as_posix() for path in raw.rglob("*") if path.is_file()}
    _require(actual == paths, "raw archive membership")
    return [root / name for name in (OBSERVATIONS, MEMBERS, PARSED_ACTS)] + [root / name for name in sorted(paths)]


def validate_evidence(root: Path, manifest: dict) -> None:
    """Verify raw member identity and every parsed/output binding without reparsing XML.

    The supported parser fingerprint is recorded, not asserted to be the current
    installed parser. Independent replay can therefore compare versions honestly.
    """
    evidence_artifacts(root, manifest)
    contract = manifest["evidence"]
    archives = _read_json(root / OBSERVATIONS)["archives"]
    members = iter(_jsonl(root / MEMBERS))
    parsed = {kind: [] for kind in contract["parsed_occurrence_counts"]}
    member_count = unresolved = 0
    for archive in archives:
        archive_parsed = []
        with tarfile.open(root / archive["raw_path"], "r:bz2") as source:
            raw_members = source.getmembers()
            _require(len(raw_members) == archive["member_count"], "raw member count")
            for ordinal, member in enumerate(raw_members):
                row = next(members, None)
                _require(row is not None, "missing raw member row")
                content = None
                if member.isfile():
                    with source.extractfile(member) as stream:
                        content = stream.read()
                identity = _member_identity(member, ordinal, content)
                _require(all(row.get(key) == value for key, value in identity.items())
                         and row.get("archive_ordinal") == archive["archive_ordinal"]
                         and row.get("archive_sha256") == archive["archive_sha256"]
                         and row.get("role") == archive["role"], "raw member identity/order/hash")
                member_count += 1
                status = row.get("parse_status")
                eligible = member.name.endswith(".xml") and (archive["role"] != "amendment_acts"
                    or Path(member.name).name.startswith(tuple(archive["prefixes"])))
                if not eligible:
                    expected = "excluded_non_xml" if not member.name.endswith(".xml") else "excluded_prefix"
                    _require(status == expected, "excluded member status")
                else:
                    _require(member.isfile() and status in ("parsed", "unresolved_missing_refid"), "eligible XML member status")
                if status == "parsed":
                    _require(isinstance(row.get("refid"), str) and re.fullmatch(r"(?:lov|forskrift)/[A-Za-z0-9][A-Za-z0-9._-]*", row["refid"])
                             and _digest(row.get("parsed_model_sha256")) and _count(row.get("parsed_occurrence_ordinal")), "parsed member identity")
                    occurrence = value_sha256([archive["archive_ordinal"], archive["archive_sha256"],
                        ordinal, member.name, row["member_sha256"], archive["role"]])
                    _require(row.get("source_occurrence_id") == occurrence, "source occurrence identity")
                    archive_parsed.append(row)
                else:
                    _require(all(row.get(key) is None for key in ("refid", "parsed_model_sha256", "parsed_occurrence_ordinal", "source_occurrence_id"))
                             and row.get("selected") is False and row.get("selected_output_path") is None
                             and row.get("selected_output_sha256") is None, "unparsed member binding")
                    unresolved += status == "unresolved_missing_refid"
        _require(len(archive_parsed) == archive["parsed_occurrence_count"], "archive parsed count")
        if archive["role"] == "amendment_acts":
            archive_parsed.sort(key=lambda row: next(i for i, prefix in enumerate(archive["prefixes"])
                if Path(row["member_path"]).name.startswith(prefix)))
        parsed[archive["role"]].extend(archive_parsed)
    _require(next(members, None) is None and member_count == contract["member_count"], "member inventory count")
    _require(unresolved == contract["unresolved_member_count"], "unresolved member count")
    selected_refs = {}
    for kind, rows in parsed.items():
        _require(len(rows) == contract["parsed_occurrence_counts"][kind], f"{kind} occurrence count")
        last = {row["refid"]: i for i, row in enumerate(rows)}
        selected_refs[kind] = set(last)
        count_name = {"laws": "law_count", "forskrifter": "forskrift_count", "amendment_acts": "amendment_act_count"}[kind]
        _require(len(last) == manifest[count_name] and len(rows) - len(last) == manifest["duplicate_counts"][kind], f"{kind} selection count")
        for i, row in enumerate(rows):
            _require(row["parsed_occurrence_ordinal"] == i and type(row.get("selected")) is bool
                     and row["selected"] == (i == last[row["refid"]]), "occurrence ordinal/last-wins selection")
            if row["selected"]:
                path = "amendments.db" if kind == "amendment_acts" else f"{kind}/{row['refid'].replace('/', '-')}.json"
                _require(row.get("selected_output_path") == path
                         and row.get("selected_output_sha256") == manifest["artifact_hashes"].get(path), "selected output hash binding")
                if kind != "amendment_acts":
                    _require(value_sha256(_read_json(root / path)) == row["parsed_model_sha256"], "selected document model hash")
            else:
                _require(row.get("selected_output_path") is None and row.get("selected_output_sha256") is None, "unselected output binding")
    with closing(sqlite3.connect((root / "amendments.db").resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        _require({row[0] for row in conn.execute("SELECT refid FROM amendment_acts")} == selected_refs["amendment_acts"], "selected amendment act membership")
    exported = iter(_jsonl(root / PARSED_ACTS))
    amendment_count = 0
    for source in parsed["amendment_acts"]:
        row = next(exported, None)
        _require(row is not None and row.get("schema_version") == PARSED_ACT_VERSION
                 and row.get("source_occurrence_id") == source["source_occurrence_id"]
                 and row.get("parsed_occurrence_ordinal") == source["parsed_occurrence_ordinal"], "parsed amendment export occurrence")
        record = row.get("record")
        _require(isinstance(record, dict) and set(record) == set(AmendmentActData.__dataclass_fields__)
                 and record.get("refid") == source["refid"]
                 and value_sha256(record) == source["parsed_model_sha256"], "complete parsed amendment model")
        for field in set(record) - {"changes_to", "amendments"}:
            _require(isinstance(record[field], str), f"parsed amendment {field}")
        _require(isinstance(record["changes_to"], list) and all(isinstance(ref, str) for ref in record["changes_to"])
                 and isinstance(record["amendments"], list), "parsed amendment lists")
        expected_occurrences = []
        for ordinal, amendment in enumerate(record["amendments"]):
            _require(isinstance(amendment, dict) and set(amendment) == set(Amendment.__dataclass_fields__)
                     and all(isinstance(value, str) for value in amendment.values()), "complete parsed amendment instruction")
            expected_occurrences.append({"ordinal": ordinal, "target_status": "identified" if amendment["target_law"] else "unresolved",
                "operation_status": "unresolved" if amendment["change_type"] == "unknown" else "identified"})
        _require(row.get("amendment_occurrences") == expected_occurrences, "amendment occurrence ordinals/status")
        _require(row.get("legal_valid_time") == {"status": "unresolved", "date": None}
                 and row.get("fidelity") == "lossless_relative_to_parsed_model"
                 and row.get("source_structure_status") == "not_verified", "amendment fidelity/time semantics")
        amendment_count += len(record["amendments"])
    _require(next(exported, None) is None and amendment_count == contract["parsed_amendment_count"], "parsed amendment export count")
