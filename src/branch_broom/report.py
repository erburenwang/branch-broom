from __future__ import annotations

import json


STATUS_LABELS = {
    "delete-candidate": "delete candidate",
    "merged-recent": "merged, still recent",
    "upstream-gone": "upstream is gone",
    "stale-unmerged": "stale, unmerged",
    "active": "active",
    "protected-current": "protected (current)",
    "protected-head": "protected (HEAD)",
    "protected-base": "protected (base)",
    "protected-worktree": "protected (worktree)",
}


def _age(value: int | None) -> str:
    return "unknown" if value is None else f"{value}d"


def _upstream(row: dict) -> str:
    if row["upstream"]:
        suffix = " (gone)" if row["upstreamGone"] else ""
        return f"{row['upstream']}{suffix}"
    return "—"


def _action(row: dict) -> str:
    action = row.get("action")
    if action == "would-delete":
        return "would delete"
    if action == "deleted":
        return "deleted"
    if action in {"refused-by-git", "skipped-missing", "skipped-changed", "skipped-protected", "skipped-worktree", "skipped-no-longer-merged"}:
        return f"{action}: {row.get('actionMessage') or ''}".rstrip()
    return "—"


def as_json(report: dict) -> str:
    public_report = {key: value for key, value in report.items() if not key.startswith("_")}
    return json.dumps(public_report, ensure_ascii=False, indent=2, sort_keys=True)


def as_text(report: dict) -> str:
    mode = "APPLY" if report["mode"] == "apply" else "DRY RUN"
    lines = [
        f"Branch Broom — {mode}",
        f"Base: {report['base']['ref']} ({report['base']['source']})",
        f"Old branch threshold: {report['staleDays']} days",
        "",
    ]

    if not report["branches"]:
        lines.append("This repository has no local branches to report.")
    else:
        lines.append(f"{'BRANCH':36} {'STATUS':24} {'AGE':8} {'UPSTREAM':28} ACTION")
        lines.append("-" * 112)
        for row in report["branches"]:
            name = row["name"]
            lines.append(
                f"{name:36} "
                f"{STATUS_LABELS.get(row['status'], row['status']):24} "
                f"{_age(row['ageDays']):8} "
                f"{_upstream(row):28} "
                f"{_action(row)}"
            )

    lines.extend(
        [
            "",
            f"{report['branchCount']} local branches; "
            f"{report['deleteCandidateCount']} cleanup candidate(s).",
        ]
    )
    if report["mode"] == "dry-run":
        lines.append("No branches changed. Review the candidates, then rerun with --apply to try safe local deletion.")
    else:
        lines.append(
            f"Apply complete: {report.get('deletedCount', 0)} deleted, "
            f"{report.get('refusedCount', 0)} refused by Git, "
            f"{report.get('skippedCount', 0)} skipped."
        )
    lines.append("Remote refs are never changed. Branches in other worktrees are protected.")
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def as_markdown(report: dict) -> str:
    mode = "apply" if report["mode"] == "apply" else "dry run"
    lines = [
        "# Branch Broom report",
        "",
        f"- Mode: **{mode}**",
        f"- Base: `{_markdown_cell(report['base']['ref'])}` ({report['base']['source']})",
        f"- Old branch threshold: {report['staleDays']} days",
        f"- Cleanup candidates: {report['deleteCandidateCount']}",
        "",
        "| Branch | Status | Age | Upstream | Action |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in report["branches"]:
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                _markdown_cell(row["name"]),
                STATUS_LABELS.get(row["status"], row["status"]),
                _age(row["ageDays"]),
                _markdown_cell(_upstream(row)),
                _markdown_cell(_action(row)),
            )
        )
    if not report["branches"]:
        lines.append("| — | — | — | — | No local branches |")
    lines.extend(
        [
            "",
            "Remote refs are never changed. Branches checked out in Git worktrees are protected.",
        ]
    )
    if report["mode"] == "dry-run":
        lines.append("This report did not change any branches.")
    return "\n".join(lines)
