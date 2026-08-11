#!/usr/bin/env bash

set -Eeuo pipefail

die() {
    echo "error: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

# -----------------------------------------------------------------------------
# Check repository
# -----------------------------------------------------------------------------

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "not inside a git repository"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

EVENT="$(basename "$ROOT")"

[[ "$EVENT" =~ ^[a-z0-9][a-z0-9-]*$ ]] ||
    die "invalid event id: $EVENT"

BRANCH="$(git branch --show-current)"

[[ "$BRANCH" == "main" ]] ||
    die "publish must be run from main (current: $BRANCH)"

[[ -z "$(git status --porcelain)" ]] ||
    die "working tree is not clean; commit or stash changes first"

git remote get-url origin >/dev/null 2>&1 ||
    die "origin remote not found"

git remote get-url upstream >/dev/null 2>&1 ||
    die "upstream remote not found"

command -v gh >/dev/null 2>&1 ||
    die "GitHub CLI (gh) is required"

gh auth status >/dev/null 2>&1 ||
    die "GitHub CLI is not authenticated"

# -----------------------------------------------------------------------------
# Publish confirmation
# -----------------------------------------------------------------------------

PUBLIC_BRANCH="event/$EVENT"
UPSTREAM_URL="$(git remote get-url upstream)"

echo
echo "Event:     $EVENT"
echo "Source:    origin/main"
echo "Publish:   upstream/$PUBLIC_BRANCH"
echo "Upstream:  $UPSTREAM_URL"
echo
echo "WARNING: This will publish the event content to the public repository."
echo

read -r -p "Continue? [y/N] " CONFIRM

[[ "$CONFIRM" =~ ^[Yy]$ ]] || {
    echo "Cancelled."
    exit 0
}

# -----------------------------------------------------------------------------
# Push public event branch
# -----------------------------------------------------------------------------

info "Publishing event/$EVENT"

git push upstream \
    "main:refs/heads/$PUBLIC_BRANCH"

# -----------------------------------------------------------------------------
# Create Pull Request
# -----------------------------------------------------------------------------

# Convert common GitHub remote formats to owner/repo.
case "$UPSTREAM_URL" in
    git@github.com:*.git)
        REPO="${UPSTREAM_URL#git@github.com:}"
        REPO="${REPO%.git}"
        ;;
    https://github.com/*.git)
        REPO="${UPSTREAM_URL#https://github.com/}"
        REPO="${REPO%.git}"
        ;;
    https://github.com/*)
        REPO="${UPSTREAM_URL#https://github.com/}"
        ;;
    *)
        die "unsupported upstream GitHub URL: $UPSTREAM_URL"
        ;;
esac

# Reuse an existing open PR if publish.sh is run again.
PR_URL="$(
    gh pr list \
        --repo "$REPO" \
        --head "$PUBLIC_BRANCH" \
        --base main \
        --state open \
        --json url \
        --jq '.[0].url // empty'
)"

if [[ -n "$PR_URL" ]]; then
    echo
    info "Pull request already exists"
    echo "$PR_URL"
    exit 0
fi

info "Creating pull request"

gh pr create \
    --repo "$REPO" \
    --head "$PUBLIC_BRANCH" \
    --base main \
    --title "content(event): $EVENT" \
    --body "Archive event \`$EVENT\` into the FloatCTF content repository."

echo
info "Published successfully"
