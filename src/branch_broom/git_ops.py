from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """A Git command or repository operation failed."""


@dataclass(frozen=True)
class BaseRef:
    ref: str
    commit: str
    source: str
    local_branch: str | None


@dataclass(frozen=True)
class LocalBranch:
    name: str
    commit: str
    committed_at: int | None
    upstream: str | None
    upstream_track: str

    @property
    def upstream_gone(self) -> bool:
        return "[gone]" in self.upstream_track.lower()


def run_git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run Git with an argument vector and no shell expansion."""
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            shell=False,
            text=True,
            timeout=20,
        )
    except FileNotFoundError as exc:
        raise GitError("Git was not found on PATH. Install Git, then retry.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("A Git command timed out after 20 seconds.") from exc
    except OSError as exc:
        raise GitError(f"Could not start Git: {exc}") from exc

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        summary = f"Git exited with code {result.returncode}"
        if detail:
            summary = f"{summary}: {detail}"
        raise GitError(summary)
    return result


def find_repo_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if not candidate.exists():
        raise GitError(f"Repository path does not exist: {candidate}")
    result = run_git(candidate, "rev-parse", "--show-toplevel")
    root = Path(result.stdout.strip()).resolve()
    if not root.is_dir():
        raise GitError("Git reported a repository root that is not a directory.")
    return root


def resolve_commit(repo: Path, ref: str) -> str:
    result = run_git(
        repo,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{ref}^{{commit}}",
    )
    commit = result.stdout.strip()
    if not commit:
        raise GitError(f"Could not resolve base ref {ref!r} to a commit.")
    return commit


def _local_branch_exists(repo: Path, name: str) -> bool:
    result = run_git(
        repo,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{name}",
        check=False,
    )
    return result.returncode == 0


def _local_name_for_base(
    ref: str,
    local_names: set[str],
    remotes: list[str],
) -> str | None:
    if ref.startswith("refs/heads/"):
        candidate = ref.removeprefix("refs/heads/")
        return candidate if candidate in local_names else None
    if ref in local_names:
        return ref

    for remote in sorted(remotes, key=len, reverse=True):
        prefix = f"{remote}/"
        if ref.startswith(prefix):
            candidate = ref[len(prefix) :]
            if candidate in local_names:
                return candidate
    return None


def resolve_base(repo: Path, requested: str | None) -> BaseRef:
    branches = list_local_branches(repo)
    names = {branch.name for branch in branches}
    remotes_result = run_git(repo, "remote")
    remotes = [line.strip() for line in remotes_result.stdout.splitlines() if line.strip()]

    if requested:
        commit = resolve_commit(repo, requested)
        return BaseRef(
            ref=requested,
            commit=commit,
            source="explicit",
            local_branch=_local_name_for_base(requested, names, remotes),
        )

    symbolic = run_git(
        repo,
        "symbolic-ref",
        "--quiet",
        "--short",
        "refs/remotes/origin/HEAD",
        check=False,
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        ref = symbolic.stdout.strip()
        try:
            commit = resolve_commit(repo, ref)
        except GitError:
            commit = ""
        if commit:
            return BaseRef(
                ref=ref,
                commit=commit,
                source="origin/HEAD",
                local_branch=_local_name_for_base(ref, names, remotes),
            )

    for candidate in ("main", "master"):
        if candidate in names and _local_branch_exists(repo, candidate):
            return BaseRef(
                ref=candidate,
                commit=resolve_commit(repo, candidate),
                source="local fallback",
                local_branch=candidate,
            )

    raise GitError(
        "Could not find origin/HEAD or a local main/master branch. "
        "Choose a base explicitly with --base <ref>."
    )


def get_current_branch(repo: Path) -> str | None:
    result = run_git(
        repo,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def get_head_commit(repo: Path) -> str:
    return resolve_commit(repo, "HEAD")


def list_local_branches(repo: Path) -> list[LocalBranch]:
    format_spec = (
        "%(refname:short)\t%(objectname)\t%(committerdate:unix)"
        "\t%(upstream:short)\t%(upstream:track)"
    )
    result = run_git(
        repo,
        "for-each-ref",
        f"--format={format_spec}",
        "refs/heads",
    )

    branches: list[LocalBranch] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 5:
            raise GitError("Git returned an unexpected local branch record.")
        name, commit, committed_at, upstream, upstream_track = fields
        try:
            timestamp = int(committed_at) if committed_at else None
        except ValueError:
            timestamp = None
        branches.append(
            LocalBranch(
                name=name,
                commit=commit,
                committed_at=timestamp,
                upstream=upstream or None,
                upstream_track=upstream_track,
            )
        )
    return branches


def list_merged_branch_names(repo: Path, base_commit: str) -> set[str]:
    result = run_git(
        repo,
        "branch",
        "--merged",
        base_commit,
        "--format=%(refname:short)",
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def list_checked_out_worktrees(repo: Path) -> set[str]:
    result = run_git(repo, "worktree", "list", "--porcelain")
    checked_out: set[str] = set()
    for line in result.stdout.splitlines():
        if line.startswith("branch refs/heads/"):
            branch = line.removeprefix("branch refs/heads/")
            checked_out.add(branch)
    return checked_out


def list_remote_names(repo: Path) -> list[str]:
    result = run_git(repo, "remote")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def branch_commit(repo: Path, name: str) -> str | None:
    result = run_git(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"refs/heads/{name}",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
