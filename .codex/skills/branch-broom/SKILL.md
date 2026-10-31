---
name: branch-broom
description: Use Branch Broom to inspect local Git branch age, merge state, worktrees, and upstream status. Use when the user asks to review or clean up branches; do not use it for remote branch deletion.
---

# Branch Broom

Use this skill when the user wants help reviewing local Git branches.

1. Confirm the command exists with `branch-broom --help`. If it is not installed, follow the uv or virtual-environment install steps in the repository README.
2. Run `branch-broom doctor --json` from the target repository, then run a read-only scan: `branch-broom --json scan --repo <path> --base <ref>`.
3. Review the selected base, candidate names, age threshold, worktree protections, and merge status. The tool does not fetch, so upstream status may be stale.
4. Summarize candidates and keep unmerged, squash-merged, or ambiguous branches for review.
5. Use `scan --apply` only when the user explicitly asked to delete local branches and the candidate list has been reviewed. This only tries ordinary `git branch -d`; never add force or remote deletion.

Examples:

```sh
branch-broom doctor --json
branch-broom --json scan --repo . --base origin/main --stale-days 60
branch-broom scan --repo . --base origin/main --stale-days 60 --apply
```

The scan is local and offline. It reads Git refs and commit metadata, not project file contents.
