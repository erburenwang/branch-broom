from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from . import __version__
from .audit import apply_cleanup, scan_repository
from .git_ops import GitError, find_repo_root
from .report import as_json, as_markdown, as_text


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a whole number") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="branch-broom",
        description=(
            "Review local Git branches safely. Scans are offline and read-only by default."
        ),
        epilog=(
            "Examples:\n"
            "  branch-broom scan\n"
            "  branch-broom scan --base origin/main --stale-days 60 --json\n"
            "  branch-broom scan --base origin/main --stale-days 60 --apply\n"
            "  branch-broom doctor --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"branch-broom {__version__}")
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="emit stable machine-readable JSON (may also follow the subcommand)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    scan = subparsers.add_parser(
        "scan",
        help="classify local branches and optionally delete old merged branches",
        description="Read local refs and report branch age, merge state, worktrees, and upstream status.",
    )
    scan.add_argument("--repo", type=Path, default=Path.cwd(), help="repository path (default: current directory)")
    scan.add_argument("--base", help="commit or ref to compare against; defaults to origin/HEAD, then local main/master")
    scan.add_argument("--stale-days", type=_non_negative_int, default=30, metavar="DAYS", help="old-branch threshold (default: 30)")
    scan.add_argument("--apply", action="store_true", help="try ordinary git branch -d on old merged local candidates")
    scan.add_argument("--json", dest="json_output", action="store_true", default=argparse.SUPPRESS, help="emit JSON")
    scan.add_argument("--markdown", action="store_true", help="emit a Markdown report")

    doctor = subparsers.add_parser(
        "doctor",
        help="check local Python, Git, and repository availability",
        description="Branch Broom is offline and does not require credentials.",
    )
    doctor.add_argument("--repo", type=Path, default=Path.cwd(), help="repository path to check (default: current directory)")
    doctor.add_argument("--json", dest="json_output", action="store_true", default=argparse.SUPPRESS, help="emit JSON")

    return parser


def _git_version() -> str | None:
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            shell=False,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _git_version_tuple(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", version)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _doctor(repo_path: Path) -> dict:
    version = _git_version()
    supported_python = sys.version_info >= (3, 11)
    parsed_git_version = _git_version_tuple(version)
    git_supported = parsed_git_version is not None and parsed_git_version >= (2, 30, 0)

    repository_found = False
    repository_error = None
    try:
        find_repo_root(repo_path)
        repository_found = True
    except GitError as exc:
        repository_error = str(exc)

    ready = supported_python and git_supported and repository_found
    return {
        "schemaVersion": 1,
        "tool": "branch-broom",
        "version": __version__,
        "ok": ready,
        "offline": True,
        "authenticationRequired": False,
        "python": {"version": sys.version.split()[0], "supported": supported_python, "requires": ">=3.11"},
        "git": {"available": version is not None, "version": version, "supported": git_supported, "requires": ">=2.30"},
        "repository": {"found": repository_found, "error": repository_error},
        "networkRequests": 0,
    }


def _emit_error(message: str, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "tool": "branch-broom",
                    "ok": False,
                    "error": {"code": "operation-failed", "message": message},
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"branch-broom: {message}", file=sys.stderr)


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "scan" and args.json_output and args.markdown:
        parser.error("--json and --markdown cannot be used together")

    if args.command == "doctor":
        result = _doctor(args.repo)
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            state = "ready" if result["ok"] else "needs attention"
            print(f"Branch Broom {result['version']} — {state}")
            print(f"Python: {result['python']['version']} (requires {result['python']['requires']})")
            print(f"Git: {result['git']['version'] or 'not found'} (requires {result['git']['requires']})")
            print(f"Repository found: {'yes' if result['repository']['found'] else 'no'}")
            print("Network: none; authentication: not required.")
            if result["repository"]["error"]:
                print(f"Repository check: {result['repository']['error']}")
        return 0 if result["ok"] else 1

    try:
        report = scan_repository(args.repo, args.base, args.stale_days)
        if args.apply:
            report = apply_cleanup(report)
    except (GitError, OSError, ValueError) as exc:
        _emit_error(str(exc), args.json_output)
        return 1

    if args.json_output:
        print(as_json(report))
    elif args.markdown:
        print(as_markdown(report))
    else:
        print(as_text(report))

    if args.apply and (report.get("refusedCount", 0) or report.get("skippedCount", 0)):
        return 1
    return 0
