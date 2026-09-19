# Development workflow

[AGENTS.md](../AGENTS.md) defines universal task rules. The
[implementation plan](implementation-plan.md) owns task scope, acceptance checks
and stop boundaries; this document owns the reusable execution and handoff process.

## Start a task

Use one branch, one worktree and one dedicated Codex session per task. Name the
session clearly after the task or branch. Resume an existing task in its existing
worktree/session; never switch branches inside a task worktree.

Before editing, inspect `git status --short --branch` and `git worktree list`, fetch
with `git fetch origin`, and compare the task HEAD with `origin/main`. Preserve
unrelated staged, unstaged and untracked work; do not automatically stash, reset,
clean or stage it. If the task already has a branch, inspect its local and remote
history before syncing; do not overwrite remote work or force-push.

Prefer the lifecycle helper, invoked from any checkout of this repository. Worktree
arguments are resolved relative to the primary BinfoCheck checkout (which must be
on `main`), regardless of the invoking checkout. The destination's parent directory
must exist. Replace the example names:

```sh
scripts/task-worktree.sh status codex/<task> ../BinfoCheck-<task>
scripts/task-worktree.sh create codex/<task> ../BinfoCheck-<task>
```

`status` is read-only: it reports path/registration and working-tree state, local
branch existence, ahead/behind and merge ancestry against `origin/main`, and remote
branch presence from the last fetch. Fetch first when fresh remote status is needed.
`create` fetches origin, requires a clean main checkout (tracked/untracked files),
refuses existing local/remote branches or worktree paths, and creates only the
branch/worktree at current `origin/main`. It does not move local main, install an
environment, push, or open a session. Underlying Git operations, from the primary
checkout after those checks, are:

```sh
git fetch --prune origin
git status --short --branch
git worktree add --no-track -b codex/<task> ../BinfoCheck-<task> origin/main
```

Open the dedicated session in that worktree. For an existing branch, locate its
worktree instead of creating a competing checkout. Read the required project and
directory instructions, state intended files/checks and blocking decisions, and
continue only the assigned scope.

## Task stages

1. **Planning:** establish scope, dependencies, required decisions and acceptance
   checks. A planning-only assignment stops with its plan/handoff.
2. **Implementation:** make the scoped changes and preserve evidence and versions.
3. **Review:** inspect the diff for correctness, scope, duplication, secrets and
   contract drift; run task checks and `scripts/verify.sh`. Fix in-scope findings.
4. **Optional live gate:** run only explicitly authorized calls within recorded
   limits. A required but blocked live gate prevents full task acceptance; it does
   not invalidate separately reported offline progress.
5. **Final review and delivery:** sync main, repeat validation as described below,
   commit, push, update the draft PR and overwrite the handoff.
6. **Merge:** only on explicit user instruction, after checking the reviewed HEAD,
   required checks and unresolved blockers. Delivery alone does not authorize merge.
7. **Cleanup:** verify the merge and preserve artifacts before authorized removal.

## Sync and conflicts

At task start and before final delivery, run:

```sh
git fetch origin
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
```

The counts are task-only (ahead) then main-only (behind). At task start, sync the
task branch with its remote and compare with main; this does not require merging
main immediately. Before final delivery, if main advanced and the worktree is ready
for integration, run `git merge origin/main` on the task branch.
Commit only your scoped work first if necessary; unrelated changes must remain
untouched. If they prevent safe integration, report that blocker.

Resolve conflicts only when the task and authoritative documents establish the
intended result. Do not discard another task's changes or weaken checks. Report
ambiguous conflicts and stop dependent work; preserve the unresolved state or
safely abort the merge without erasing pre-existing edits. After integration,
review the combined result and rerun task acceptance/regression checks and
`scripts/verify.sh`. Never repeat a live call merely because main changed; its
existing authorization and remaining limits must cover it.

## Offline verification and live boundaries

Run from the repository root:

```sh
scripts/verify.sh
```

The script fails at the first failed command and uses the existing locked uv
environment for tests, lint, formatting, types, schema drift and both staged and
unstaged whitespace checks. It makes no network/provider/model calls and adds no
dependencies. Python and locked dependencies must already be available locally;
if offline setup fails, report the missing prerequisite instead of silently
installing over the network. Task-specific acceptance checks remain additional.

Live provider/model calls require explicit task or user authorization specifying
request and cost limits. Credentials and prior successful calls are not permission.
Record the authorized inputs, provider/model settings, timeout, concurrency and
retry caps before execution. Do not retry an uncertain paid timeout unless the same
authorization permits it. Stop at limits, preserve failures/partial outcomes, and
record actual usage and cost; missing usage stays unknown. Report offline, live
and deployed checks separately. Keep detailed capture/live evidence in dedicated
reports referenced by the handoff.

## Private artifacts

Keep restricted captures, stores and reports outside tracked/shareable fixtures.
Never include secrets in commits, PRs or handoffs. Before removing a worktree,
identify ignored/untracked artifacts and preserve any required evidence in an
appropriate durable private location. Verify it remains usable and record only the
paths/IDs needed to resume, with origins where relevant. `/tmp` handoffs are
resumability notes, not durable evidence storage. Do not delete the only copy of
raw evidence, version history or unfinished work.

## Standard delivery

Review `git diff` and the staged diff, stage only intended files, and commit the
scoped result. Push the task branch (`git push -u origin codex/<task>` for its first
publication) and create or update a draft PR targeting `main`. Respect assignments
that explicitly stop before publication. Keep its title/body current: describe the
problem, final behavior, validation and remaining blockers without turn history.
Inspect CI for the exact pushed HEAD and report passed, failed or pending truthfully.
Do not describe a pending check as passed or a draft PR as merged.

Record the exact commit, changed files, validation, PR/CI state and fetched main
comparison in the handoff. If main advances again before delivery, merge it and
repeat validation and publication. Never merge the PR as part of standard delivery.

## Handoffs

Overwrite `/tmp/binfocheck-<task>-handoff.txt`; do not append stale history.
Handoffs are resumability records, not complete task histories. Use the task ID or
bounded maintenance name in the heading. Default structure:

```text
# TXX handoff

Status:
Branch:
Worktree:
PR:
Head:
Main comparison:

## What changed
- Concise bullets for this turn only, including changed files.

## New decisions / invariants
- Only newly introduced or changed decisions; reference committed docs for older ones.

## Verification
- Task tests:
- Full tests, if run:
- Lint/type/schema:
- CI:
- Live calls/cost:

## Essential artifacts
- Only paths/IDs needed to continue.

## Blockers
- Current blockers only.

## Next step
- One concise action.
```

Use explicit not-run/not-applicable states where needed. Do not repeat information
already preserved in architecture, docs or commits, or list every historical
artifact. Keep detailed live/capture evidence in dedicated reports. Longer
handoffs are justified only when evidence is not preserved elsewhere or a live or
security-sensitive operation needs detailed audit information.

## Post-merge cleanup

After an explicitly authorized merge, fetch origin and verify the PR's merged
state and result on `origin/main` (accounting for squash/rebase merge history).
Update the handoff with that state and any preserved artifact locations. Inspect
worktree status, including ignored/private files, and check for unpushed commits
before removal. Preserve unfinished work and durable private evidence first.

Within explicitly authorized cleanup scope, leave the task worktree and prefer:

```sh
scripts/task-worktree.sh cleanup codex/<task> ../BinfoCheck-<task>
```

The helper fetches origin and checks all preconditions before removal: the path
must be the registered task worktree, unlocked and clean, including ignored files.
Preserve private evidence first and explicitly handle disposable caches/environments;
the helper never removes them for you. The local branch must be an ancestor of
`origin/main`. If its remote branch exists, the two tips must match; if absent,
ancestry in `origin/main` proves the commits are already pushed. Squash/rebase
merges without that ancestry are refused and need manual review.

Cleanup then removes the worktree, deletes the local branch, deletes the remote
branch if present, and verifies path, registration and branch absence. Underlying
Git operations after those checks are:

```sh
git merge-base --is-ancestor codex/<task> origin/main
git worktree remove ../BinfoCheck-<task>
git -c branch.codex/<task>.remote=origin -c branch.codex/<task>.merge=refs/heads/main branch -d codex/<task>
git push origin --delete codex/<task>
git worktree list
git branch --list codex/<task>
git ls-remote --heads origin refs/heads/codex/<task>
```

The temporary branch configuration makes Git's non-forced deletion check use the
verified `origin/main` even when local main is stale; no stored configuration is
changed. The helper never targets `main`, uses force deletion, or closes a Codex
session. Run lifecycle operations without concurrent edits/pushes to the same task.
Failures stop immediately; cleanup is not transactional, so inspect `status` and
finish any remaining authorized steps manually after a partial failure. Paths
requiring Git's quoted porcelain encoding are refused for manual handling.

Sync the main checkout with a fast-forward only when clean and not in use by
another session. Close/archive the task session manually once its resumability
record is complete. If cleanup is not authorized or cannot be done safely, report
the remaining worktree/branch instead of deleting it.

The helper's isolated local-repository tests run as part of `scripts/verify.sh`, or
alone with `uv run --offline --locked pytest tests/workflow`. They require no
network access, credentials or provider calls.
