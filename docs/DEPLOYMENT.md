# Gold Cup Leaderboard Deployment

This note covers the one-time setup needed on the Drupal host after the leaderboard
JSON URL, Drupal root, and destination node ID are known.

For details on how rendered HTML is passed to Drush and environment-size limits,
see [DRUPAL_UPDATE_TRANSPORT_DESIGN.md](DRUPAL_UPDATE_TRANSPORT_DESIGN.md).

## Prerequisites

- Python 3 available as `/usr/bin/python3`
- `drush` available on the SSH user's `PATH`, or a known absolute path
- A Drupal Basic Page node already created for the leaderboard
- The node body text format set to `Full HTML`
- A stable public JSON URL that serves the approved schema

## Suggested server layout

Example paths:

```text
~/deploy/GBSC-Gold-Cup-via-WinScore/
~/scripts/update_leaderboard.py
~/scripts/gc_update.sh
~/scripts/leaderboard.env
~/scripts/gold_cup_state.txt
~/logs/leaderboard.log
```

The script can live anywhere outside the webroot. The state file is created
automatically on first successful non-dry-run update.

## Install scripts

Copy [scripts/update_leaderboard.py](../scripts/update_leaderboard.py) and [scripts/gc_update.sh](../scripts/gc_update.sh) to the Drupal host and make them executable:

```bash
chmod 755 ~/scripts/update_leaderboard.py
chmod 755 ~/scripts/gc_update.sh
mkdir -p ~/logs
```

If you keep this repository checked out on the server, you can also copy from the repo checkout:

```bash
mkdir -p ~/scripts
cp ~/deploy/GBSC-Gold-Cup-via-WinScore/scripts/update_leaderboard.py ~/scripts/
cp ~/deploy/GBSC-Gold-Cup-via-WinScore/scripts/gc_update.sh ~/scripts/
chmod 755 ~/scripts/update_leaderboard.py ~/scripts/gc_update.sh
```

## Customize gc_update.sh

Edit `~/scripts/gc_update.sh` for your account path and verify it points at your repo checkout:

```bash
# inside ~/scripts/gc_update.sh
export USER_HOME="/home/<your-user>"
```

The script expects these files after customization:

- `"$USER_HOME/scripts/leaderboard.env"`
- `"$USER_HOME/scripts/update_leaderboard.py"`

The script also expects `REPO_DIR` and `BRANCH` to be set in `leaderboard.env` so it can run:

```bash
git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
```

## Environment file

Create `~/scripts/leaderboard.env`:

```bash
export LEADERBOARD_JSON_URL="https://example.com/path/to/leaderboard.json"
export DRUPAL_ROOT="/path/to/drupal/root"
export DRUPAL_URI="https://www.soargbsc.net"
export DRUPAL_NODE_ID="123"
export DRUSH_BIN="/usr/local/bin/drush"
export REPO_DIR="$HOME/deploy/GBSC-Gold-Cup-via-WinScore"
export BRANCH="main"
```

Notes:

- `LEADERBOARD_JSON_URL` must stay stable between updates.
- `DRUPAL_ROOT` is the filesystem path containing Drupal's `index.php`.
- `DRUPAL_NODE_ID` is the numeric node ID of the leaderboard page.
- `DRUSH_BIN` is optional if `drush` is already on the `PATH`.
- `REPO_DIR` and `BRANCH` are required by `gc_update.sh` for the pre-update `git pull`.

## Preflight validation

Run one dry-run fetch before touching Drupal:

```bash
source ~/scripts/leaderboard.env
/usr/bin/python3 ~/scripts/update_leaderboard.py --dry-run --verbose
```

That command should fetch and validate the JSON and render the HTML in memory
without updating Drupal or writing the state file.

If you want to inspect the rendered markup first:

```bash
source ~/scripts/leaderboard.env
/usr/bin/python3 ~/scripts/update_leaderboard.py \
  --dry-run \
  --write-html ~/scripts/leaderboard_preview.html
```

## First live run

After the dry run succeeds:

```bash
/bin/bash ~/scripts/gc_update.sh
```

Expected behavior:

- Drupal node body is replaced with the rendered leaderboard HTML.
- `~/scripts/gold_cup_state.txt` is written with the current `generated_at` value.
- Later runs exit cleanly without updating Drupal when `generated_at` is unchanged.

## Cron entry

Given the current expectation of infrequent updates, a daily run is a reasonable
starting point:

```cron
# Update GBSC Gold Cup leaderboard once per day at 06:15 server time
15 6 * * * /bin/bash "$HOME/scripts/gc_update.sh" >> "$HOME/logs/leaderboard.log" 2>&1
```

If you want a different cadence, keep the same command and only change the cron schedule.

## Symlink guidance

Using symlinks from `~/scripts` to files under `~/deploy/GBSC-Gold-Cup-via-WinScore` is a reasonable pattern and not inherently unwise.

Benefits:

- Single source of truth in the repo checkout.
- Easier updates when you pull new code.

Risks and mitigations:

- A bad deploy or partial pull can affect cron immediately: run updates in a controlled window, then run a manual test.
- Broken links stop automation: validate links with `ls -l ~/scripts` after deploys.
- Path assumptions in scripts still matter: keep `USER_HOME`, `REPO_DIR`, and executable paths consistent.

If uptime risk is a concern, keep `~/scripts/gc_update.sh` as a regular file and only symlink `update_leaderboard.py`.

## Pre-deploy checklist

Before pulling changes or replacing scripts on the server:

1. Back up the currently running cron wrapper script:

  ```bash
  cp ~/scripts/gc_update.sh ~/scripts/gc_update.sh.bak.$(date +%Y%m%d-%H%M%S)
  ```

2. Confirm the environment file still contains required values:

  ```bash
  grep -E '^(export )?(LEADERBOARD_JSON_URL|DRUPAL_ROOT|DRUPAL_URI|DRUPAL_NODE_ID|REPO_DIR|BRANCH)=' ~/scripts/leaderboard.env
  ```

3. Run a dry-run validation with the deployed script:

  ```bash
  source ~/scripts/leaderboard.env
  /usr/bin/python3 ~/scripts/update_leaderboard.py --dry-run --verbose
  ```

4. If using symlinks, verify current link targets before changing anything:

  ```bash
  ls -l ~/scripts
  ```

## Post-deploy checklist

After any pull or script update on the server:

1. Confirm symlinks resolve as expected:

  ```bash
  ls -l ~/scripts
  ```

2. Confirm the repo is on the intended branch and clean:

  ```bash
  git -C ~/deploy/GBSC-Gold-Cup-via-WinScore status -sb
  ```

3. Run one manual update and verify success before waiting for cron:

  ```bash
  /bin/bash ~/scripts/gc_update.sh
  ```

4. Verify the expected outputs were updated:

  ```bash
  ls -l ~/output.html ~/gold_cup_state.txt
  ```

5. Tail the log after the next cron window to confirm unattended execution:

  ```bash
  tail -n 100 ~/logs/leaderboard.log
  ```

## Manual commands

Force a local HTML preview without touching Drupal:

```bash
source ~/scripts/leaderboard.env
/usr/bin/python3 ~/scripts/update_leaderboard.py \
  --dry-run \
  --write-html ~/scripts/leaderboard_preview.html
```

Run against a local JSON file instead of the network source:

```bash
/usr/bin/python3 ~/scripts/update_leaderboard.py \
  --json-file ./data/leaderboard_sample.json \
  --dry-run \
  --write-html ./data/leaderboard_sample.html
```

## Failure modes to expect

- Missing `scoring_summary`, `flights_grouped_by_pilot`, or `generated_at`: script exits non-zero.
- Invalid date or time formats: script exits non-zero.
- Missing Drupal settings on a live run: script exits non-zero before calling `drush`.
- Missing node or `drush` failure: script exits non-zero and leaves the previous state file untouched.