#!/usr/bin/env bash
#set -x

set -Eeuo pipefail

# Cron often provides a minimal PATH; include common locations.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

date

export USER_HOME="/home/david"
ENV_FILE="$USER_HOME/scripts/leaderboard.env"
PY_SCRIPT="$USER_HOME/scripts/update_leaderboard.py"
OUTPUT_HTML="$USER_HOME/output.html"
STATE_FILE="$USER_HOME/gold_cup_state.txt"

if [[ ! -r "$ENV_FILE" ]]; then
       echo "ERROR: Required env file is missing or unreadable: $ENV_FILE" >&2
       exit 1
fi

source "$ENV_FILE"

: "${REPO_DIR:?ERROR: REPO_DIR is not set by $ENV_FILE}"
: "${BRANCH:?ERROR: BRANCH is not set by $ENV_FILE}"

if [[ ! -d "$REPO_DIR/.git" ]]; then
       echo "ERROR: REPO_DIR does not look like a git repo: $REPO_DIR" >&2
       exit 1
fi

if ! command -v git >/dev/null 2>&1; then
       echo "ERROR: git is not available on PATH" >&2
       exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
       echo "ERROR: python3 is not available on PATH" >&2
       exit 1
fi

if ! git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"; then
       echo "ERROR: git pull failed for branch $BRANCH in repo $REPO_DIR" >&2
       exit 1
fi

if ! python3 "$PY_SCRIPT" --write-html "$OUTPUT_HTML" \
       --verbose --state-file "$STATE_FILE"; then
       echo "ERROR: leaderboard update script failed" >&2
       exit 1
fi
