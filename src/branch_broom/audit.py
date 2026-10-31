from __future__ import annotations

import time
from pathlib import Path

from .git_ops import (
    GitError,
    branch_commit,
    find_repo_root,
    get_current_branch,
    get_head_commit,
    list_checked_out_worktrees,
    list_local_branches,
    list_merged_branch_names,
    resolve_base,
    run_git,
)


def scan_repository(
    path: Path,
    requested_base: str | None,
    stale_days: int,
    *,
    now: int | None = None,
) -> dict:
    if stale_days < 0:
        raise GitError("--stale-days must be zero or greater.")

    repo = find_repo_root(path)
    base = resolve_base(repo, requested_base)
    branches = list_local_branches(repo)
    merged_names = list_merged_branch_names(repo, base.commit)
    checked_out = list_checked_out_worktrees(repo)
    current = get_current_branch(repo)
    head_commit = get_head_commit(repo)
    timestamp_now = int(time.time()) if now is None else now

    rows: list[dict] = []
    for branch in branches:
        if branch.committed_at is None:
            age_days = None
        else:
            age_days = max(0, (timestamp_now - branch.committed_at) // 86_400)

        is_merged = branch.name in merged_names
        in_worktree = branch.name in checked_out
        if branch.name == current:
            status = "protected-current"
        elif current is None and branch.commit == head_commit:
            status = "protected-head"
        elif branch.name == base.local_branch:
            status = "protected-base"
        elif in_worktree:
            status = "protected-worktree"
        elif is_merged:
            if age_days is not None and age_days >= stale_days:
                status = "delete-candidate"
            else:
                status = "merged-recent"
        elif branch.upstream_gone:
            status = "upstream-gone"
        elif age_days is not None and age_days >= stale_days:
            status = "stale-unmerged"
        else:
            status = "active"

        rows.append(
            {
                "name": branch.name,
                "status": status,
                "ageDays": age_days,
                "upstream": branch.upstream,
                "upstreamGone": branch.upstream_gone,
                "mergedIntoBase": is_merged,
                "checkedOutInWorktree": in_worktree,
                "deleteCandidate": status == "delete-candidate",
                "commit": branch.commit,
                "action": "would-delete" if status == "delete-candidate" else None,
                "actionMessage": None,
            }
        )

    rows.sort(key=lambda row: (row["status"], row["name"].casefold(), row["name"]))
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    return {
        "schemaVersion": 1,
        "tool": "branch-broom",
        "ok": True,
        "offline": True,
        "mode": "dry-run",
        "base": {
            "ref": base.ref,
            "commit": base.commit,
            "source": base.source,
            "protectedLocalBranch": base.local_branch,
        },
        "staleDays": stale_days,
        "branchCount": len(rows),
        "deleteCandidateCount": sum(row["deleteCandidate"] for row in rows),
        "statusCounts": status_counts,
        "branches": rows,
        "notes": [
            "Remote-tracking refs are read as-is; this command does not fetch or prune.",
            "A delete candidate is still passed to ordinary git branch -d; Git may refuse it.",
            "Only local branches are considered. Remote refs are never changed.",
        ],
        "_repoPath": str(repo),
    }


def apply_cleanup(report: dict) -> dict:
    repo = Path(report["_repoPath"])
    report["mode"] = "apply"
    deleted = 0
    refused = 0
    skipped = 0

    for branch in report["branches"]:
        if not branch["deleteCandidate"]:
            continue

        name = branch["name"]
        current = get_current_branch(repo)
        worktrees = list_checked_out_worktrees(repo)
        latest_base_commit = resolve_base(repo, report["base"]["ref"]).commit
        current_commit = branch_commit(repo, name)

        if current_commit is None:
            branch["action"] = "skipped-missing"
            branch["actionMessage"] = "The branch was removed before apply began."
            skipped += 1
            continue
        if current_commit != branch["commit"]:
            branch["action"] = "skipped-changed"
            branch["actionMessage"] = "The branch tip changed after the scan."
            skipped += 1
            continue
        if name == current or name == report["base"]["protectedLocalBranch"]:
            branch["action"] = "skipped-protected"
            branch["actionMessage"] = "The branch became the current or base branch."
            skipped += 1
            continue
        if name in worktrees:
            branch["action"] = "skipped-worktree"
            branch["actionMessage"] = "The branch is checked out in a Git worktree."
            branch["checkedOutInWorktree"] = True
            skipped += 1
            continue

        ancestor = run_git(
            repo,
            "merge-base",
            "--is-ancestor",
            current_commit,
            latest_base_commit,
            check=False,
        )
        if ancestor.returncode != 0:
            branch["action"] = "skipped-no-longer-merged"
            branch["actionMessage"] = "The branch is no longer merged into the selected base."
            skipped += 1
            continue

        deletion = run_git(repo, "branch", "-d", "--", name, check=False)
        if deletion.returncode == 0:
            branch["action"] = "deleted"
            branch["actionMessage"] = "Deleted local branch with ordinary git branch -d."
            deleted += 1
        else:
            branch["action"] = "refused-by-git"
            branch["actionMessage"] = (
                (deletion.stderr or deletion.stdout).strip()
                or "Git refused to delete this local branch."
            )
            refused += 1

    report["deletedCount"] = deleted
    report["refusedCount"] = refused
    report["skippedCount"] = skipped
    report["summary"] = {
        "deleteCandidates": report["deleteCandidateCount"],
        "deleted": deleted,
        "refusedByGit": refused,
        "skipped": skipped,
    }
    return report


