#!/usr/bin/env bash
#set -x
date
export USER_HOME="/home/david/"
source $USER_HOME/scripts/leaderboard.env
git -C $REPO_DIR pull --ff-only origin "$BRANCH"
python3 $USER_HOME/scripts/update_leaderboard.py --write-html $USER_HOME/output.html \
       --verbose --state-file $USER_HOME/gold_cup_state.txt
