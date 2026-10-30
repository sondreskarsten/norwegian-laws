"""Command-line entry point."""
from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .repo import ENV_CACHE, ENV_NO_UPDATE, ENV_REMOTE, ENV_REPO, Repo
from .server import create_server


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="norwegian-laws-mcp",
        description="MCP server over the norwegian-laws Git repository.",
        epilog=(
            f"Environment: {ENV_REPO} (existing checkout), {ENV_REMOTE} (clone URL), "
            f"{ENV_CACHE} (cache directory), {ENV_NO_UPDATE}=1 (never fetch on start)."
        ),
    )
    p.add_argument("--repo", help="Path to an existing checkout. Default: clone into the cache directory.")
    p.add_argument("--remote", help="Git URL to clone from (default: the GitHub repository).")
    p.add_argument("--cache-dir", help="Where the managed clone lives (default: ~/.cache/norwegian-laws-mcp).")
    p.add_argument("--update", action="store_true", help="Fetch on start even for a user-provided checkout.")
    p.add_argument("--no-update", action="store_true", help="Do not fetch on start.")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--path", default="/mcp", help="HTTP path for streamable-http.")
    p.add_argument("--prepare-only", action="store_true", help="Clone/update the data and exit.")
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    update: bool | None = None
    if args.update:
        update = True
    if args.no_update:
        update = False
    repo = Repo.from_settings(repo=args.repo, remote=args.remote, cache_dir=args.cache_dir, update=update)
    if args.prepare_only:
        repo.prepare_sync()
        head = repo.head()
        print(f"{repo.path}: HEAD {head.sha[:10]} {head.date} {head.subject}")
        return 0
    repo.start()
    server = create_server(repo)
    if args.transport == "streamable-http":
        server.run(transport="streamable-http", host=args.host, port=args.port, streamable_http_path=args.path,
                   stateless_http=True, json_response=True)
    else:
        server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
