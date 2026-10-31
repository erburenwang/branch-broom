# Branch Broom

**See which local Git branches are safe to review before you clean them up.**

[![Checks](https://github.com/erburenwang/branch-broom/actions/workflows/ci.yml/badge.svg)](https://github.com/erburenwang/branch-broom/actions/workflows/ci.yml)

Branch Broom makes a local, offline report of branch age, merge state, worktrees, and upstream status. A scan never changes a branch. Cleanup is an explicit `--apply` operation limited to old branches already merged into the selected base.

## What it does

- Finds the base from `origin/HEAD`, with a local `main` or `master` fallback, or accepts `--base` explicitly.
- Identifies old merged candidates, recent merges, stale unmerged branches, branches whose upstream is gone, and active branches.
- Protects the current branch, selected base branch, and branches checked out in another Git worktree.
- Supports readable, JSON, and Markdown reports.
- Uses ordinary `git branch -d`; it never force-deletes a branch or changes a remote ref.
- Makes no network requests and requires no credentials or runtime packages.

## Install

Install the public GitHub source as a command with [uv](https://docs.astral.sh/uv/guides/tools/):

```sh
uv tool install git+https://github.com/erburenwang/branch-broom.git
```

Or clone the repository and install it with Python:

```sh
git clone https://github.com/erburenwang/branch-broom.git
cd branch-broom
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install .
```

Requires Python 3.11 or newer and Git 2.30 or newer.

## Use

Start with a read-only scan:

```sh
branch-broom scan
```

Choose the base and age threshold explicitly when useful:

```sh
branch-broom scan --base origin/main --stale-days 60
branch-broom scan --base main --markdown
branch-broom --json scan --repo ../another-project
branch-broom doctor --json
```

The default age threshold is 30 days. It uses each branch tip's committer date. Upstream status comes from the remote-tracking refs already on disk; Branch Broom does not fetch or prune them. Run `git fetch --prune` yourself first if you want to refresh that information.

### Apply cleanup

Review a dry-run report first. If you explicitly want to remove eligible **local** branches, run:

```sh
branch-broom scan --base origin/main --stale-days 60 --apply
```

`--apply` only tries branches that are merged into the selected base and at least the age threshold. Branch Broom checks the branch again immediately before deletion and uses `git branch -d`. Git can still refuse a deletion, for example when its own upstream/HEAD safety check does not consider the branch integrated. A refused branch is left in place. Remote branches, worktree branches, the current branch, and the selected base are not deleted.

## Report statuses

| Status | Meaning |
| --- | --- |
| `delete-candidate` | Merged into the selected base, old enough, and not protected |
| `merged-recent` | Merged, but newer than the age threshold |
| `upstream-gone` | Not merged into the selected base; its configured upstream is marked gone |
| `stale-unmerged` | Older than the threshold and not merged into the selected base |
| `active` | Not old enough to be called stale and not merged |
| `protected-current` | Checked out in the current worktree |
| `protected-base` | The local branch corresponding to the selected base |
| `protected-worktree` | Checked out in another Git worktree |
| `protected-head` | Points at HEAD while HEAD is detached |

Merge detection follows Git commit ancestry. A branch merged by squash or rebase may not be recognized as merged; it remains for review and is never automatically treated as a deletion candidate.

## JSON and exit codes

Use `--json` before or after the subcommand. Successful scans return a versioned envelope containing `base`, `staleDays`, `branchCount`, `deleteCandidateCount`, `statusCounts`, and a `branches` array. Each branch includes its name, status, age, upstream state, commit ID, eligibility, and action result.

An operational error returns `{"schemaVersion":1,"tool":"branch-broom","ok":false,"error":{"code":"operation-failed","message":"..."}}` on stdout. The CLI uses exit code `0` for a completed scan, `1` for an operation error or incomplete apply, and `2` for invalid arguments. `doctor` returns a nonzero code when Python, Git, or repository detection needs attention.

Reports contain local branch names and commit IDs. Review them before sharing outside your team.

## Privacy

Branch Broom only reads local Git refs and metadata. It does not read file contents, contact a Git host, run a fetch, or send telemetry. The only write operation is the opt-in deletion of eligible local branch refs through `git branch -d`.

## Codex companion skill

The repository includes a short Codex skill at `.codex/skills/branch-broom/SKILL.md` for scanning first and treating cleanup as an explicit user-authorized action.

## License

MIT. See [LICENSE](LICENSE).

---

# Branch Broom（简体中文）

**先看清本地 Git 分支，再决定哪些可以清理。**

Branch Broom 在本机离线生成分支年龄、合并状态、worktree 和上游状态报告。扫描默认只读；只有显式使用 `--apply`，才会尝试删除已合并且达到旧分支时间阈值的本地分支。

## 功能

- 默认从 `origin/HEAD` 确定基准分支；找不到时尝试本地 `main` 或 `master`，也可以用 `--base` 指定。
- 标出旧的已合并候选、近期合并、长期未合并、上游已删除和活跃分支。
- 保护当前分支、基准分支和在其他 Git worktree 中检出的分支。
- 支持普通文本、JSON 和 Markdown 报告。
- 使用普通的 `git branch -d`，不强制删除，也不修改远端分支。
- 不联网、不需要凭据，也没有运行时依赖。

## 安装

使用 [uv](https://docs.astral.sh/uv/guides/tools/) 从公开 GitHub 仓库安装：

```sh
uv tool install git+https://github.com/erburenwang/branch-broom.git
```

也可以克隆仓库后用 Python 安装：

```sh
git clone https://github.com/erburenwang/branch-broom.git
cd branch-broom
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install .
```

需要 Python 3.11 及以上版本和 Git 2.30 及以上版本。

## 使用

先运行只读扫描：

```sh
branch-broom scan
```

需要时手动指定基准分支和时间阈值：

```sh
branch-broom scan --base origin/main --stale-days 60
branch-broom scan --base main --markdown
branch-broom --json scan --repo ../another-project
branch-broom doctor --json
```

默认阈值为 30 天，以分支尖端提交的提交者时间计算。上游状态来自本机现有的远端跟踪引用；工具不会 fetch 或 prune。需要刷新时，请先自行运行 `git fetch --prune`。

### 执行清理

先检查只读报告。明确要删除符合条件的**本地**分支时，运行：

```sh
branch-broom scan --base origin/main --stale-days 60 --apply
```

`--apply` 只尝试删除已合并到所选基准且达到时间阈值的分支。删除前会重新检查分支，并使用 `git branch -d`。如果 Git 的上游/HEAD 安全检查认为分支尚未集成，Git 会拒绝删除，分支会保留。远端分支、其他 worktree 中的分支、当前分支和基准分支都不会被删除。

## 状态说明

| 状态 | 含义 |
| --- | --- |
| `delete-candidate` | 已合并到基准、达到时间阈值且未受保护 |
| `merged-recent` | 已合并，但还没有达到时间阈值 |
| `upstream-gone` | 未合并到基准，配置的上游已标记为删除 |
| `stale-unmerged` | 超过时间阈值且未合并到基准 |
| `active` | 未达到过期阈值，也未合并 |
| `protected-current` | 当前 worktree 正在检出 |
| `protected-base` | 与所选基准对应的本地分支 |
| `protected-worktree` | 在其他 Git worktree 中检出 |
| `protected-head` | HEAD 分离时指向当前 HEAD 的分支 |

合并检测基于 Git 提交祖先关系。Squash 或 rebase 合并可能无法被识别；此时分支会保留供你复核，不会被当作可删候选。

## JSON 和退出码

`--json` 可以放在子命令前或后。成功扫描返回带版本的对象，包含 `base`、`staleDays`、`branchCount`、`deleteCandidateCount`、`statusCounts` 和 `branches` 数组。每个分支包含名称、状态、年龄、上游信息、提交 ID、删除资格和操作结果。

运行错误会在 stdout 返回带 `schemaVersion`、`ok:false` 和 `error` 的 JSON 对象。完整扫描退出码为 `0`；操作错误或部分清理失败为 `1`；参数错误为 `2`。`doctor` 在 Python、Git 或仓库检测需要处理时返回非零码。

报告会包含本地分支名和提交 ID。对外分享前请先检查内容。

## 隐私

Branch Broom 只读取本地 Git 引用和元数据，不读取文件内容、不联系 Git 托管服务、不执行 fetch，也不发送遥测。唯一的写操作是用户通过 `--apply` 明确触发后，使用 `git branch -d` 删除符合条件的本地分支引用。

## Codex 配套技能

仓库包含 `.codex/skills/branch-broom/SKILL.md`，指导 Codex 先扫描，并把清理视为需要用户明确授权的操作。

## 许可

MIT，见 [LICENSE](LICENSE)。
