#!/usr/bin/env bash
# Worktree helper for parallel task work. See AGENTS.md, "Parallel work with worktrees".
#
#   scripts/wt.sh new TASK-ID [--owner WHO] [--push]   claim the task on the current (integration)
#                                                      branch, commit the claim, create branch + worktree
#   scripts/wt.sh list                                 worktrees and in-progress tasks
#   scripts/wt.sh path TASK-ID                         print the worktree path for a task
#   scripts/wt.sh remove TASK-ID [--delete-branch]     remove a finished task's worktree
#
# Worktrees live outside the repo so tools that scan the tree don't see duplicates:
#   ${PALMS_WORKTREE_ROOT:-<repo-parent>/<repo-name>-worktrees}/<TASK-ID>
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
NAME="$(basename "$ROOT")"
WT_ROOT="${PALMS_WORKTREE_ROOT:-$(dirname "$ROOT")/${NAME}-worktrees}"
TASKS="python3 $ROOT/scripts/tasks.py"

die() { echo "wt.sh: $*" >&2; exit 1; }

task_field() { # task_field ID key
  sed -n "/^---$/,/^---$/p" "$ROOT/tracking/tasks/$1.md" | sed -n "s/^$2:[[:space:]]*//p" | head -1 | tr -d '"'
}

slugify() { tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-40 | sed -E 's/-+$//'; }

cmd="${1:-}"; shift || true
case "$cmd" in
  new)
    id="${1:-}"; shift || die "usage: wt.sh new TASK-ID [--owner WHO] [--push]"
    owner="${USER:-agent}"; push=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --owner) owner="$2"; shift 2 ;;
        --push) push=1; shift ;;
        *) die "unknown option $1" ;;
      esac
    done
    [ -f "$ROOT/tracking/tasks/$id.md" ] || die "no task $id"
    git -C "$ROOT" diff --quiet -- tracking/tasks || die "uncommitted changes under tracking/tasks; commit or stash first"
    base="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
    slug="$(task_field "$id" title | slugify)"
    branch="task/$(echo "$id" | tr '[:upper:]' '[:lower:]')-$slug"
    path="$WT_ROOT/$id"
    [ -e "$path" ] && die "worktree path exists: $path"
    $TASKS claim "$id" --owner "$owner" --branch "$branch" --worktree "$path"
    git -C "$ROOT" add "tracking/tasks/$id.md"
    git -C "$ROOT" commit -q -m "chore(tracking): claim $id for $owner" -m "branch: $branch"
    if [ "$push" = 1 ]; then
      # The push is the lock: if someone else claimed first, this is rejected.
      if ! git -C "$ROOT" push -q origin "$base"; then
        git -C "$ROOT" reset -q --hard HEAD~1
        die "push rejected; another session may have claimed tasks. Run: git pull --rebase, then re-check $id"
      fi
    fi
    mkdir -p "$WT_ROOT"
    git -C "$ROOT" worktree add -q -b "$branch" "$path" HEAD
    echo "worktree: $path"
    echo "branch:   $branch (from $base)"
    echo "next:     cd \"$path\" && python3 scripts/tasks.py show $id"
    ;;
  list)
    git -C "$ROOT" worktree list
    echo
    $TASKS list --status in_progress
    ;;
  path)
    id="${1:-}"; [ -n "$id" ] || die "usage: wt.sh path TASK-ID"
    echo "$WT_ROOT/$id"
    ;;
  remove)
    id="${1:-}"; shift || die "usage: wt.sh remove TASK-ID [--delete-branch]"
    path="$WT_ROOT/$id"
    branch="$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    git -C "$ROOT" worktree remove "$path"
    if [ "${1:-}" = "--delete-branch" ] && [ -n "$branch" ]; then
      git -C "$ROOT" branch -d "$branch" || echo "branch $branch not fully merged; kept"
    fi
    git -C "$ROOT" worktree prune
    ;;
  *)
    sed -n '2,12p' "$0"; exit 1 ;;
esac
