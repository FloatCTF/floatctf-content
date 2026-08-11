#!/usr/bin/env bash

set -Eeuo pipefail

PRIVATE_REPO_URL="${1:-}"

die() {
    echo "error: $*" >&2
    exit 1
}

[[ -n "$PRIVATE_REPO_URL" ]] ||
    die "usage: $0 <private-repo-url>"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "not inside a git repository"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

EVENT="$(basename "$ROOT")"

# 初始化 Event 工作目录
mkdir -p challenges gameboxes events

# event/base -> main
CURRENT_BRANCH="$(git branch --show-current)"

[[ "$CURRENT_BRANCH" == "event/base" ]] ||
    die "expected branch 'event/base', got '$CURRENT_BRANCH'"

git branch -m main

# 公共仓库成为 upstream
git remote rename origin upstream

# 私有比赛仓库成为 origin
git remote add origin "$PRIVATE_REPO_URL"

echo
echo "Event initialized: $EVENT"
echo
echo "Branch:"
git branch --show-current
echo
echo "Remotes:"
git remote -v
