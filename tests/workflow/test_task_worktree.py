"""Exercise the shell helper against disposable local Git repositories only."""

import os
import shlex
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/task-worktree.sh"


def run(cwd: Path, *args: str, success: bool = True) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == success, output
    return output


def git(cwd: Path, *args: str) -> str:
    return run(cwd, "git", *args).strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    remote = tmp_path / "origin.git"
    main = tmp_path / "main checkout"
    run(tmp_path, "git", "init", "--bare", "--initial-branch=main", str(remote))
    run(tmp_path, "git", "clone", str(remote), str(main))
    git(main, "config", "user.name", "Workflow Test")
    git(main, "config", "user.email", "workflow@example.invalid")
    (main / ".gitignore").write_text("private/\n")
    git(main, "add", ".gitignore")
    git(main, "commit", "-m", "Initial")
    git(main, "push", "-u", "origin", "main")
    return main


def helper(
    repo: Path,
    command: str,
    branch: str = "codex/task",
    *,
    success: bool = True,
    path: str = "../task worktree",
) -> str:
    return run(repo, "bash", str(SCRIPT), command, branch, path, success=success)


def task_path(repo: Path) -> Path:
    return repo.parent / "task worktree"


def commit_task(repo: Path) -> None:
    task = task_path(repo)
    (task / "change.txt").write_text("task change\n")
    git(task, "add", "change.txt")
    git(task, "commit", "-m", "Task")


def publish_and_merge(repo: Path) -> None:
    git(task_path(repo), "push", "-u", "origin", "codex/task")
    git(repo, "merge", "--no-ff", "codex/task", "-m", "Merge task")
    git(repo, "push", "origin", "main")


def assert_preserved(repo: Path) -> None:
    assert task_path(repo).is_dir()
    git(repo, "show-ref", "--verify", "refs/heads/codex/task")


def test_create_status_cleanup(repo: Path) -> None:
    helper(repo, "create")
    assert git(task_path(repo), "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")
    output = helper(repo, "status")
    assert "Worktree registration: matches branch" in output
    assert "Local branch: present" in output
    assert "Ahead/behind origin/main: 0\t0" in output
    assert "Merged into origin/main: yes" in output
    assert "Remote branch (last fetched): absent" in output
    commit_task(repo)
    publish_and_merge(repo)
    output = helper(repo, "status")
    assert "Remote branch (last fetched): present" in output
    assert "Cleanup verified" in helper(repo, "cleanup")
    assert not task_path(repo).exists()
    assert not git(repo, "branch", "--list", "codex/task")
    assert not git(repo, "ls-remote", "--heads", "origin", "refs/heads/codex/task")
    assert "Worktree path: absent" in helper(repo, "status")


@pytest.mark.parametrize("dirt", ["tracked", "staged", "untracked", "ignored"])
def test_dirty_worktree_refused(repo: Path, dirt: str) -> None:
    helper(repo, "create")
    publish_and_merge(repo)
    task = task_path(repo)
    if dirt in ("tracked", "staged"):
        (task / ".gitignore").write_text("changed\n")
        if dirt == "staged":
            git(task, "add", ".gitignore")
    elif dirt == "ignored":
        (task / "private").mkdir()
        (task / "private" / "evidence").write_text("preserve\n")
    else:
        (task / "untracked").write_text("preserve\n")
    assert "dirty or contains ignored" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)
    assert git(repo, "ls-remote", "--heads", "origin", "refs/heads/codex/task")


def test_status_omits_ignored_files_but_cleanup_still_refuses(repo: Path) -> None:
    helper(repo, "create")
    publish_and_merge(repo)
    task = task_path(repo)
    (task / "private").mkdir()
    (task / "private" / "evidence").write_text("preserve\n")

    output = helper(repo, "status")
    assert "private/evidence" not in output
    assert "!!" not in output

    assert "dirty or contains ignored" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)


def test_unmerged_branch_refused(repo: Path) -> None:
    helper(repo, "create")
    commit_task(repo)
    git(task_path(repo), "push", "-u", "origin", "codex/task")
    assert "Merged into origin/main: no" in helper(repo, "status")
    assert "not merged" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)


def test_unpushed_task_commit_refused_even_when_on_main(repo: Path) -> None:
    helper(repo, "create")
    git(task_path(repo), "push", "-u", "origin", "codex/task")
    commit_task(repo)
    git(repo, "merge", "codex/task")
    git(repo, "push", "origin", "main")
    assert "Local/remote branch differ" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)


@pytest.mark.parametrize("command", ["create", "status", "cleanup"])
def test_main_refused(repo: Path, command: str) -> None:
    assert "Refusing main" in helper(repo, command, "main", success=False)
    assert "Refusing the main checkout" in helper(repo, command, path=str(repo), success=False)


def test_existing_branch_or_path_refused(repo: Path) -> None:
    git(repo, "branch", "codex/task")
    assert "Local branch already exists" in helper(repo, "create", success=False)
    git(repo, "branch", "-d", "codex/task")
    task_path(repo).mkdir()
    assert "already exists" in helper(repo, "create", success=False)
    assert not git(repo, "branch", "--list", "codex/task")
    task_path(repo).rmdir()
    helper(repo, "create")
    assert "already exists" in helper(repo, "create", "codex/other", success=False)
    assert not git(repo, "branch", "--list", "codex/other")


def test_remote_branch_refused(repo: Path) -> None:
    git(repo, "push", "origin", "main:refs/heads/codex/task")
    assert "Remote branch already exists" in helper(repo, "create", success=False)
    assert not task_path(repo).exists()


def test_dirty_main_refused(repo: Path) -> None:
    (repo / "unfinished").write_text("keep\n")
    assert "Main checkout is dirty" in helper(repo, "create", success=False)
    assert not task_path(repo).exists()


def test_create_uses_current_origin_main_from_task_checkout(repo: Path) -> None:
    old = git(repo, "rev-parse", "HEAD")
    (repo / "new").write_text("new main\n")
    git(repo, "add", "new")
    git(repo, "commit", "-m", "Advance main")
    git(repo, "push", "origin", "main")
    current = git(repo, "rev-parse", "HEAD")
    git(repo, "reset", "--hard", old)  # Disposable fixture only: simulate stale local main.
    helper(repo, "create")
    assert git(task_path(repo), "rev-parse", "HEAD") == current
    assert git(repo, "rev-parse", "HEAD") == old
    assert "matches branch" in helper(task_path(repo), "status")
    assert "Cleanup verified" in helper(repo, "cleanup")  # No task remote; already on main.


def test_wrong_worktree_and_locked_worktree_refused(repo: Path) -> None:
    helper(repo, "create")
    assert "does not match" in helper(repo, "cleanup", path="../wrong", success=False)
    git(repo, "worktree", "lock", str(task_path(repo)))
    assert "locked" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)


def test_remote_only_commits_preserved(repo: Path) -> None:
    helper(repo, "create")
    publish_and_merge(repo)
    original = git(task_path(repo), "rev-parse", "HEAD")
    commit_task(repo)
    git(task_path(repo), "push", "origin", "codex/task")
    git(task_path(repo), "reset", "--hard", original)  # Disposable fixture only.
    assert "Local/remote branch differ" in helper(repo, "cleanup", success=False)
    assert_preserved(repo)


def test_stale_worktree_registration_refused(repo: Path) -> None:
    helper(repo, "create")
    task_path(repo).rename(repo.parent / "moved without git")
    assert "already exists" in helper(repo, "create", "codex/other", success=False)
    assert not git(repo, "branch", "--list", "codex/other")


def test_remote_advance_during_cleanup_preserved(repo: Path) -> None:
    helper(repo, "create")
    commit_task(repo)
    publish_and_merge(repo)
    remote = repo.parent / "origin.git"
    racer = repo.parent / "concurrent checkout"
    git(repo, "clone", "--branch", "codex/task", str(remote), str(racer))
    git(racer, "config", "user.name", "Concurrent Test")
    git(racer, "config", "user.email", "concurrent@example.invalid")
    (racer / "unseen.txt").write_text("preserve concurrent work\n")
    git(racer, "add", "unseen.txt")
    git(racer, "commit", "-m", "Concurrent work")
    new_tip = git(racer, "rev-parse", "HEAD")

    # Advance the remote immediately before it advertises refs for the deletion push.
    # Also refresh tracking refs: the lease must use the saved SHA, not a moving ref.
    receiver = repo.parent / "receive-with-concurrent-push.sh"
    receiver.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"test ! -d {shlex.quote(str(task_path(repo)))}\n"
        f"git -C {shlex.quote(str(racer))} push origin HEAD:refs/heads/codex/task >&2\n"
        f"git -C {shlex.quote(str(repo))} fetch origin >&2\n"
        'exec git-receive-pack "$@"\n'
    )
    git(repo, "config", "remote.origin.receivepack", f"bash {shlex.quote(str(receiver))}")
    output = helper(repo, "cleanup", success=False)
    assert "stale info" in output
    assert "worktree/local branch already removed" in output
    assert "Cleanup verified" not in output
    assert not task_path(repo).exists()
    assert not git(repo, "branch", "--list", "codex/task")
    assert git(remote, "rev-parse", "refs/heads/codex/task") == new_tip
    assert git(remote, "show", "refs/heads/codex/task:unseen.txt") == "preserve concurrent work"
    assert git(repo, "rev-parse", "refs/remotes/origin/codex/task") == new_tip
    assert "Remote branch (last fetched): present" in helper(repo, "status")
