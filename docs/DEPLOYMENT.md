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
~/scripts/update_leaderboard.py
~/scripts/leaderboard.env
~/scripts/leaderboard_state.json
~/logs/leaderboard.log
```

The script can live anywhere outside the webroot. The state file is created
automatically on first successful non-dry-run update.

## Install the script

Copy [scripts/update_leaderboard.py](c:\Users\david\Google%20Drive\Soaring\GBSC\GBSC-Gold-Cup-via-WinScore\scripts\update_leaderboard.py) to the Drupal host and make it executable:

```bash
chmod 755 ~/scripts/update_leaderboard.py
mkdir -p ~/logs
```

## Environment file

Create `~/scripts/leaderboard.env`:

```bash
export LEADERBOARD_JSON_URL="https://example.com/path/to/leaderboard.json"
export DRUPAL_ROOT="/path/to/drupal/root"
export DRUPAL_URI="https://www.soargbsc.net"
export DRUPAL_NODE_ID="123"
export DRUSH_BIN="/usr/local/bin/drush"
```

Notes:

- `LEADERBOARD_JSON_URL` must stay stable between updates.
- `DRUPAL_ROOT` is the filesystem path containing Drupal's `index.php`.
- `DRUPAL_NODE_ID` is the numeric node ID of the leaderboard page.
- `DRUSH_BIN` is optional if `drush` is already on the `PATH`.

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
source ~/scripts/leaderboard.env
/usr/bin/python3 ~/scripts/update_leaderboard.py --verbose
```

Expected behavior:

- Drupal node body is replaced with the rendered leaderboard HTML.
- `~/scripts/leaderboard_state.json` is written with the current `generated_at` value.
- Later runs exit cleanly without updating Drupal when `generated_at` is unchanged.

## Cron entry

Given the current expectation of infrequent updates, a daily run is a reasonable
starting point:

```cron
# Update GBSC Gold Cup leaderboard once per day at 06:15 server time
15 6 * * * . "$HOME/scripts/leaderboard.env"; /usr/bin/python3 "$HOME/scripts/update_leaderboard.py" >> "$HOME/logs/leaderboard.log" 2>&1
```

If you want a different cadence, keep the same command and only change the cron schedule.

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