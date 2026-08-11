#!/usr/bin/env bash

set -Eeuo pipefail

PRIVATE_REPO_URL="${1:-}"

die() {
    echo "error: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

[[ -n "$PRIVATE_REPO_URL" ]] ||
    die "usage: $0 <private-repo-url>"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "not inside a git repository"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

EVENT="$(basename "$ROOT")"

[[ "$EVENT" =~ ^[a-z0-9][a-z0-9-]*$ ]] ||
    die "invalid event id: $EVENT"

CURRENT_BRANCH="$(git branch --show-current)"

case "$CURRENT_BRANCH" in
    "event/base")
        info "Renaming branch event/base -> main"
        git branch -m main
        ;;
    "main")
        ;;
    *)
        die "expected branch 'event/base' or 'main', got '$CURRENT_BRANCH'"
        ;;
esac

# The cloned event/base branch tracks the public repository.
# Remove that tracking so an accidental `git push` cannot publish anything.
git branch --unset-upstream >/dev/null 2>&1 || true

# -----------------------------------------------------------------------------
# Directories
# -----------------------------------------------------------------------------

info "Creating event directories"

mkdir -p \
    challenges \
    gameboxes \
    events

# -----------------------------------------------------------------------------
# Event manifest
# -----------------------------------------------------------------------------

EVENT_FILE="events/${EVENT}.toml"

if [[ ! -e "$EVENT_FILE" ]]; then
    info "Creating $EVENT_FILE"

    cat >"$EVENT_FILE" <<EOF
schema_version = 1

id = "$EVENT"
title = ""
description = ""
started_at = ""
ended_at = ""

# BEGIN GENERATED CONTENT
[content]
challenges = []
gameboxes = []
# END GENERATED CONTENT
EOF
else
    info "Keeping existing $EVENT_FILE"
fi

# -----------------------------------------------------------------------------
# Remotes
# -----------------------------------------------------------------------------

if git remote get-url upstream >/dev/null 2>&1; then
    info "Keeping existing upstream"
elif git remote get-url origin >/dev/null 2>&1; then
    info "Renaming origin -> upstream"
    git remote rename origin upstream
else
    die "no origin or upstream remote found"
fi

if git remote get-url origin >/dev/null 2>&1; then
    info "Setting origin -> $PRIVATE_REPO_URL"
    git remote set-url origin "$PRIVATE_REPO_URL"
else
    info "Adding origin -> $PRIVATE_REPO_URL"
    git remote add origin "$PRIVATE_REPO_URL"
fi

echo
echo "Initialized event: $EVENT"
echo
echo "Manifest:"
echo "  $EVENT_FILE"
echo
echo "Remotes:"
git remote -v
echo
echo "Next:"
echo "  git add ."
echo "  git commit -m \"chore: initialize event\""
echo "  git push -u origin main"
