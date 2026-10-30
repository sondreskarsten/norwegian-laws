"""Access to a checkout of the norwegian-laws repository."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import GitError, NotReadyError

log = logging.getLogger(__name__)

DEFAULT_REMOTE = "https://github.com/sondreskarsten/norwegian-laws.git"
DEFAULT_BRANCH = "main"
DOC_DIRS = ("lover", "forskrifter")
HISTORIE_DIR = "historie"
CATALOG_FILE = "laws.json"
ENV_REPO = "NORWEGIAN_LAWS_REPO"
ENV_REMOTE = "NORWEGIAN_LAWS_REMOTE"
ENV_CACHE = "NORWEGIAN_LAWS_CACHE"
ENV_NO_UPDATE = "NORWEGIAN_LAWS_NO_UPDATE"


def default_cache_dir() -> Path:
    base = os.environ.get(ENV_CACHE)
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return root / "norwegian-laws-mcp"


@dataclass
class Commit:
    sha: str
    date: str
    subject: str

    @property
    def short(self) -> str:
        return self.sha[:10]

    @property
    def day(self) -> str:
        return self.date[:10]


@dataclass
class RevInfo:
    """A resolved revision and how the request was interpreted."""

    sha: str
    date: str
    requested: str
    clamped_to_first: bool = False
    clamped_to_last: bool = False

    @property
    def day(self) -> str:
        return self.date[:10]


DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Repo:
    """A Git checkout of the laws repository.

    ``managed`` checkouts live in the cache directory, are created by this
    package with a blobless single-branch clone, and are reset to the remote
    branch on update. User-provided checkouts are only fast-forwarded on an
    explicit update.
    """

    def __init__(
        self,
        path: Path,
        *,
        remote: str = DEFAULT_REMOTE,
        branch: str = DEFAULT_BRANCH,
        managed: bool = False,
        update_on_start: bool = False,
    ) -> None:
        self.path = Path(path)
        self.remote = remote
        self.branch = branch
        self.managed = managed
        self.update_on_start = update_on_start
        self._ready = threading.Event()
        self._error: str | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_update: dict | None = None

    @classmethod
    def from_settings(
        cls,
        repo: str | None = None,
        remote: str | None = None,
        cache_dir: str | None = None,
        update: bool | None = None,
    ) -> "Repo":
        repo = repo or os.environ.get(ENV_REPO)
        remote = remote or os.environ.get(ENV_REMOTE) or DEFAULT_REMOTE
        no_update_env = os.environ.get(ENV_NO_UPDATE, "").lower() in {"1", "true", "yes"}
        if repo:
            return cls(
                Path(repo).expanduser(),
                remote=remote,
                managed=False,
                update_on_start=bool(update) and not no_update_env,
            )
        cache = Path(cache_dir).expanduser() if cache_dir else default_cache_dir()
        return cls(
            cache / "norwegian-laws",
            remote=remote,
            managed=True,
            update_on_start=(update is not False) and not no_update_env,
        )

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Prepare the checkout in a background thread."""
        self._thread = threading.Thread(target=self._prepare, name="laws-repo-prepare", daemon=True)
        self._thread.start()

    def _prepare(self) -> None:
        try:
            with self._lock:
                if not self.is_checkout():
                    if self.managed:
                        self.clone()
                    else:
                        raise GitError(
                            f"{self.path} is not a Git checkout of the norwegian-laws repository. "
                            f"Point {ENV_REPO} at a clone, or unset it to let the server clone into the cache."
                        )
                elif self.update_on_start:
                    try:
                        self.update()
                    except GitError as exc:
                        log.warning("update on start failed, serving existing checkout: %s", exc)
        except Exception as exc:  # noqa: BLE001 - surfaced to tools
            self._error = str(exc)
            log.error("repository preparation failed: %s", exc)
        finally:
            self._ready.set()

    def ready(self, timeout: float | None = 600) -> None:
        if not self._ready.wait(timeout):
            raise NotReadyError("The repository is still being cloned; try again in a moment.")
        if self._error:
            raise NotReadyError(f"The repository is unavailable: {self._error}")

    def prepare_sync(self) -> None:
        self._prepare()
        self.ready(0)

    # -- git plumbing ----------------------------------------------------

    def is_checkout(self) -> bool:
        return (self.path / ".git").exists() and (self.path / CATALOG_FILE).exists()

    def git(self, *args: str, check: bool = True, cwd: Path | None = None, timeout: int = 600) -> str:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C.UTF-8", LANG="C.UTF-8")
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(cwd or self.path),
                env=env,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise GitError("git is not installed or not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args[:2])} timed out after {timeout}s") from exc
        out = proc.stdout.decode("utf-8", errors="replace")
        if check and proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            raise GitError(f"git {' '.join(args)} failed: {err or proc.returncode}")
        return out

    def clone(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="norwegian-laws-", dir=str(self.path.parent)))
        target = tmp / "repo"
        log.info("cloning %s into %s (blobless, branch %s)", self.remote, self.path, self.branch)
        started = time.time()
        try:
            self.git(
                "clone", "--quiet", "--filter=blob:none", "--single-branch",
                "--branch", self.branch, self.remote, str(target),
                cwd=tmp, timeout=3600,
            )
            if self.is_checkout():
                shutil.rmtree(tmp, ignore_errors=True)
                return
            target.rename(self.path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        log.info("clone finished in %.0fs", time.time() - started)

    def update(self) -> dict:
        """Fetch the remote branch and move the checkout to it."""
        before = self.head()
        if self.managed:
            self.git("fetch", "--quiet", "origin", self.branch, timeout=3600)
            self.git("reset", "--quiet", "--hard", f"origin/{self.branch}")
        else:
            self.git("pull", "--quiet", "--ff-only", timeout=3600)
        after = self.head()
        self.last_update = {
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "before": before.sha,
            "after": after.sha,
            "changed": before.sha != after.sha,
        }
        return self.last_update

    def head(self) -> Commit:
        out = self.git("log", "-1", "--date=iso-strict", "--format=%H%x1f%ad%x1f%s", "HEAD").strip()
        sha, date, subject = out.split("\x1f", 2)
        return Commit(sha, date, subject)

    def commit_count(self) -> int:
        return int(self.git("rev-list", "--count", "HEAD").strip() or 0)

    def is_shallow(self) -> bool:
        return self.git("rev-parse", "--is-shallow-repository").strip() == "true"

    def history_bounds(self) -> tuple[Commit, Commit]:
        """First and last commit reachable from HEAD (cached per HEAD)."""
        head = self.head()
        cached = getattr(self, "_bounds", None)
        if cached and cached[1].sha == head.sha:
            return cached
        out = self.git("log", "--reverse", "--date=iso-strict", "--format=%H%x1f%ad%x1f%s", "HEAD").split("\n", 1)[0]
        sha, date, subject = out.strip().split("\x1f", 2)
        self._bounds = (Commit(sha, date, subject), head)
        return self._bounds

    def resolve_rev_info(self, spec: str | None) -> RevInfo:
        """Resolve a commit-ish, ISO date, or approximate date.

        Dates resolve to the last commit on or before that day. A date before the
        first commit is clamped to the first commit and flagged; a date after HEAD
        is clamped to HEAD and flagged.
        """
        first, last = self.history_bounds()
        if not spec or spec.strip().upper() == "HEAD":
            return RevInfo(last.sha, last.date, spec or "HEAD")
        spec = spec.strip()
        out = self.git("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}", check=False).strip()
        if out:
            date = self.git("log", "-1", "--date=iso-strict", "--format=%ad", out).strip()
            return RevInfo(out, date, spec)
        before_spec = f"{spec}T23:59:59" if DATE_ONLY_RE.match(spec) else spec
        probe = self.git("rev-list", "-1", f"--before={before_spec}", "HEAD", check=False).strip()
        if probe:
            date = self.git("log", "-1", "--date=iso-strict", "--format=%ad", probe).strip()
            return RevInfo(probe, date, spec, clamped_to_last=(probe == last.sha and DATE_ONLY_RE.match(spec) is not None and spec > last.day))
        # git accepted the date syntax but nothing is older: check that the spec is a date at all
        check = self.git("rev-list", "-1", f"--after={before_spec}", "HEAD", check=False)
        if check.strip() or DATE_ONLY_RE.match(spec):
            return RevInfo(first.sha, first.date, spec, clamped_to_first=True)
        raise GitError(
            f"Could not resolve '{spec}' to a commit. Use a commit sha, HEAD~N, an ISO date like "
            f"2026-10-01, or a phrase like '2 weeks ago'."
        )

    def resolve_rev(self, spec: str | None) -> str:
        return self.resolve_rev_info(spec).sha

    def show(self, rev: str, relpath: str) -> str | None:
        """Return the file content at ``rev`` or None when it did not exist there."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C.UTF-8", LANG="C.UTF-8")
        proc = subprocess.run(
            ["git", "show", f"{rev}:{relpath}"], cwd=str(self.path), env=env, capture_output=True, timeout=600,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8", errors="replace")

    def removal_commit(self, relpath: str) -> Commit | None:
        """The commit that deleted ``relpath`` from the branch, if it is gone from HEAD."""
        if self.exists(relpath):
            return None
        out = self.git("log", "-1", "--diff-filter=D", "--date=iso-strict", "--format=%H%x1f%ad%x1f%s",
                       "HEAD", "--", relpath, check=False).strip()
        if not out:
            return None
        sha, date, subject = out.split("\x1f", 2)
        return Commit(sha, date, subject)

    def removed_files(self, prefixes: tuple[str, ...]) -> list[tuple[str, Commit]]:
        """Every file under the prefixes deleted somewhere in the branch history and absent from HEAD."""
        out = self.git("log", "--diff-filter=D", "--date=iso-strict", "--format=%x1e%H%x1f%ad%x1f%s",
                       "--name-only", "HEAD", "--", *prefixes, check=False)
        result: list[tuple[str, Commit]] = []
        seen: set[str] = set()
        for block in out.split("\x1e"):
            block = block.strip("\n")
            if not block:
                continue
            header, _, body = block.partition("\n")
            parts = header.split("\x1f")
            if len(parts) < 3:
                continue
            commit = Commit(parts[0], parts[1], parts[2])
            for line in body.split("\n"):
                path = line.strip()
                if path and path not in seen and not self.exists(path):
                    seen.add(path)
                    result.append((path, commit))
        return result

    def ensure_version_tags(self) -> list[str]:
        """Fetch the law-history yearly and build tags (commits only; trees and blobs on demand)."""
        if getattr(self, "_version_tags", None) is None:
            self.git("fetch", "--quiet", "--filter=tree:0", "origin",
                     "+refs/tags/v20*:refs/tags/v20*", "+refs/tags/history-*:refs/tags/history-*",
                     check=False, timeout=600)
            tags = self.git("tag", "-l", "v20*", "history-*", check=False).split()
            self._version_tags = sorted(tags)
        return self._version_tags

    def read(self, relpath: str) -> str:
        target = self.path / relpath
        if not target.is_file():
            raise GitError(f"{relpath} does not exist in the checkout")
        return target.read_text(encoding="utf-8")

    def exists(self, relpath: str) -> bool:
        return (self.path / relpath).is_file()
