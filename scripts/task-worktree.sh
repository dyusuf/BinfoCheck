#!/usr/bin/env bash
set -euo pipefail

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ $# == 3 ]] || fail 'Usage: task-worktree.sh {status|create|cleanup} <branch> <worktree>'
command=$1
branch=$2
case "$command" in status|create|cleanup) ;; *) fail "Unknown command: $command" ;; esac
[[ "$branch" != main && "$branch" != -* ]] || fail 'Refusing main or an option-like branch name.'
git check-ref-format "refs/heads/$branch" >/dev/null || fail 'Invalid branch name.'

# Resolve the primary checkout from the shared Git directory, even from a task worktree.
common=$(git rev-parse --path-format=absolute --git-common-dir)
main=$(cd -- "$common/.." && pwd -P)
[[ $(git -C "$main" rev-parse --show-toplevel) == "$main" ]] || fail 'Primary checkout not found.'
[[ $(git -C "$main" symbolic-ref --quiet --short HEAD) == main ]] || fail 'Primary checkout must be on main.'
cd -- "$main"
# Require an existing parent; canonicalize it so aliases cannot target the main checkout.
parent=$(cd -- "$(dirname -- "$3")" && pwd -P)
worktree=$parent/$(basename -- "$3")
[[ -d "$worktree" ]] && worktree=$(cd -- "$worktree" && pwd -P)
[[ "$worktree" != "$main" && "$worktree" != "$main/"* ]] || fail 'Refusing the main checkout or a path inside it.'
[[ "$worktree" != */. && "$worktree" != */.. ]] || fail 'Invalid worktree path.'

exists() { git show-ref --verify --quiet "$1"; }
registered_path=
path_registered=false
locked=false
# Older Git versions lack worktree-list -z; refuse quoted paths instead of decoding them.
records=$(git -c core.quotePath=false worktree list --porcelain)
path=
while IFS= read -r field; do
    case "$field" in
        'worktree '*)
            path=${field#worktree }
            [[ "$path" != "$worktree" ]] || path_registered=true
            [[ "$path" != \"* ]] || fail 'Quoted worktree paths require manual handling.'
            ;;
        "branch refs/heads/$branch") registered_path=$path ;;
        locked*) [[ "$path" != "$worktree" ]] || locked=true ;;
    esac
done <<< "$records"

# Status is read-only and reports the last fetched remote state.
if [[ "$command" == status ]]; then
    printf 'Main checkout: %s\nWorktree: %s\n' "$main" "$worktree"
    if [[ -e "$worktree" || -L "$worktree" ]]; then
        printf 'Worktree path: present\n'
        if [[ "$registered_path" == "$worktree" ]]; then
            printf 'Worktree registration: matches branch (locked: %s)\n' "$locked"
            git -C "$worktree" status --short --branch --untracked-files=all --ignored
        else
            printf 'Worktree registration: does not match branch\n'
        fi
    else
        printf 'Worktree path: absent\n'
    fi
    printf 'Branch worktree: %s\n' "${registered_path:-none}"
    if exists "refs/heads/$branch"; then
        printf 'Local branch: present\n'
        if exists refs/remotes/origin/main; then
            printf 'Ahead/behind origin/main: '
            git rev-list --left-right --count "refs/heads/$branch...refs/remotes/origin/main"
            if git merge-base --is-ancestor "refs/heads/$branch" refs/remotes/origin/main; then
                printf 'Merged into origin/main: yes\n'
            else
                printf 'Merged into origin/main: no\n'
            fi
        else
            printf 'Ahead/behind origin/main: unknown\nMerged into origin/main: unknown\n'
        fi
    else
        printf 'Local branch: absent\nAhead/behind origin/main: n/a\nMerged into origin/main: n/a\n'
    fi
    if exists "refs/remotes/origin/$branch"; then
        printf 'Remote branch (last fetched): present\n'
    else
        printf 'Remote branch (last fetched): absent\n'
    fi
    exit 0
fi

git fetch --prune origin 'refs/heads/*:refs/remotes/origin/*'
exists refs/remotes/origin/main || fail 'origin/main is unavailable.'
if [[ "$command" == create ]]; then
    main_state=$(git status --porcelain --untracked-files=all)
    [[ -z "$main_state" ]] || fail 'Main checkout is dirty.'
    ! exists "refs/heads/$branch" || fail 'Local branch already exists.'
    ! exists "refs/remotes/origin/$branch" || fail 'Remote branch already exists.'
    [[ ! -e "$worktree" && ! -L "$worktree" && -z "$registered_path" && "$path_registered" == false ]] || fail 'Branch/worktree already exists.'
    # Git also refuses stale registrations and paths occupied by other worktrees.
    git worktree add --no-track -b "$branch" "$worktree" refs/remotes/origin/main
    exit 0
fi

# All preconditions precede removal. Ignored files may contain private evidence.
exists "refs/heads/$branch" || fail 'Local branch is absent.'
[[ "$registered_path" == "$worktree" && -d "$worktree" ]] || fail 'Worktree does not match the task branch.'
[[ "$locked" == false ]] || fail 'Worktree is locked.'
task_state=$(git -C "$worktree" status --porcelain --untracked-files=all --ignored)
[[ -z "$task_state" ]] || fail 'Worktree is dirty or contains ignored files.'
git merge-base --is-ancestor "refs/heads/$branch" refs/remotes/origin/main || fail 'Branch is not merged into origin/main.'
remote_present=false
if exists "refs/remotes/origin/$branch"; then
    remote_present=true
    [[ $(git rev-parse "refs/heads/$branch") == $(git rev-parse "refs/remotes/origin/$branch") ]] || fail 'Local/remote branch differ; refusing unpushed commits or remote work.'
fi
# If the task remote is already absent, ancestry in origin/main proves every commit is pushed.
git worktree remove -- "$worktree"
# Use the verified origin/main as the deletion safety check, without changing branch config.
git -c "branch.$branch.remote=origin" -c "branch.$branch.merge=refs/heads/main" branch -d -- "$branch"
if [[ "$remote_present" == true ]]; then
    git push origin --delete "$branch"
fi
[[ ! -e "$worktree" && ! -L "$worktree" ]] || fail 'Worktree path remains.'
! exists "refs/heads/$branch" || fail 'Local branch remains.'
records=$(git -c core.quotePath=false worktree list --porcelain)
while IFS= read -r field; do
    [[ "$field" != "worktree $worktree" ]] || fail 'Worktree registration remains.'
done <<< "$records"
remaining=$(git ls-remote --heads origin "refs/heads/$branch")
[[ -z "$remaining" ]] || fail 'Remote branch remains.'
printf 'Cleanup verified: %s (%s)\n' "$branch" "$worktree"
