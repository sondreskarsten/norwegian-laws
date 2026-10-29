"""Access to a checkout of the norwegian-laws repository."""
from __future__ import annotations

import logging
import os
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

    def resolve_rev(self, spec: str | None) -> str:
        """Resolve a commit-ish, ISO date, or approximate date to a commit sha."""
        if not spec or spec.upper() == "HEAD":
            return self.head().sha
        spec = spec.strip()
        out = self.git("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}", check=False).strip()
        if out:
            return out
        before = self.git("rev-list", "-1", f"--before={spec}", "HEAD", check=False).strip()
        if before:
            return before
        raise GitError(
            f"Could not resolve '{spec}' to a commit. Use a commit sha, HEAD~N, an ISO date like "
            f"2026-10-01, or a phrase like '2 weeks ago'."
        )

    def show(self, rev: str, relpath: str) -> str | None:
        """Return the file content at ``rev`` or None when it did not exist there."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C.UTF-8", LANG="C.UTF-8")
        proc = subprocess.run(
            ["git", "show", f"{rev}:{relpath}"], cwd=str(self.path), env=env, capture_output=True, timeout=600,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8", errors="replace")

    def read(self, relpath: str) -> str:
        target = self.path / relpath
        if not target.is_file():
            raise GitError(f"{relpath} does not exist in the checkout")
        return target.read_text(encoding="utf-8")

    def exists(self, relpath: str) -> bool:
        return (self.path / relpath).is_file()
