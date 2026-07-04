# GBSC Gold Cup Leaderboard — Project Plan

## Overview

The Greater Boston Soaring Club (GBSC) runs a season-long "Gold Cup" soaring contest:
https://www.soargbsc.net/gold_cup_contest

Scoring is done manually by the club's contest manager using WinScore (a Windows desktop
scoring application). The contest manager will periodically export a JSON file reflecting
the current leaderboard. This project automates the display of that leaderboard on the
club's Drupal website (soargbsc.net) by fetching the JSON and updating a Drupal page,
with no manual web-editing step required after the initial setup.

## Scope of this project

**In scope:**
- A cron script (Python) running on the Drupal host that fetches the JSON, formats it
  as HTML, and pushes it into a Drupal node via drush
- A Drupal content node to hold the leaderboard
- Initial setup/configuration of the cron job and Drupal node

**Out of scope (possible future phase):**
- Member self-service IGC flight submission and automated scoring
- Reimplementing WinScore's scoring logic in Python
- Any changes to the contest manager's existing WinScore workflow

The out-of-scope items were discussed at length and remain technically viable. The
decision to descope them reflects the practical reality that the JSON+cron approach
delivers a useful leaderboard with far less development effort.
A separate planning document exists covering the full scoring app design if that phase
is ever revisited.

## Architecture

```
Contest manager runs WinScore manually (unchanged)
        │
        ▼
Contest manager exports leaderboard as JSON and publishes it
to a stable public URL (exact URL TBD — see open questions)
        │
        ▼
Cron job on Drupal host (Python script, runs on a schedule)
  - fetches JSON from the public URL
  - validates basic structure (guards against fetching a broken/partial file)
  - exits if internal `generated_at` timestamp is unchanged
  - renders JSON into an HTML leaderboard (standings table + per-pilot flight details)
  - calls drush to update the body field of a specific Drupal node
        │
        ▼
Drupal page (Basic Page node, body field updated in place)
displays the leaderboard — no modules, no REST API, no external services
```

### Why this architecture

- **No new Drupal modules required** — this approach uses only drush (already installed) and a cron job.
- **No public-facing API or inbound network connections** — the script makes only
  outbound HTTP GET requests to fetch the JSON. No ports opened, no endpoints exposed.
- **No credentials leave the Drupal host** — drush runs locally with its own Drupal
  database access. The cron script holds no database passwords or API tokens.
- **Minimal attack surface** — adds exactly one new thing: a cron job running a small
  script. Same trust model as Drupal's own cron jobs already running on the server.
- **Self-contained** — no Railway account, no external services, no dependencies beyond
  Python standard library + drush.

## JSON schema

The contest manager produces the JSON file. The agreed schema is as follows.

### Top-level structure

```json
{
  "scoring_summary": [...],
  "flights_grouped_by_pilot": {...},
  "generated_at": "2026-07-03T14:31:30.416409"
}
```

- `generated_at`: ISO 8601 datetime string. Displayed on the leaderboard page as
  "Last updated: ..." so members know how fresh the data is.

### `scoring_summary` (array, sorted descending by score)

One entry per pilot who has submitted at least one scoring flight. Array order is
meaningful (first entry = current leader) but rank should be computed from scores in
the rendering code rather than trusted from position, to handle ties correctly.

```json
{
  "Pilot": "Glen Kelley",
  "Score (best three)": 1884,
  "Flights of": ["2026-04-26", "2026-06-24"]
}
```

- `Pilot`: string, pilot's full name
- `Score (best three)`: integer, sum of pilot's best 3 flight scores (or all flights
  if fewer than 3 have been submitted)
- `Flights of`: **array of ISO 8601 date strings** (`YYYY-MM-DD`) — the dates of the
  flights contributing to the score. Requested as an array (not a comma-separated
  string) to allow hyperlinking dates to flight detail rows.

### `flights_grouped_by_pilot` (object, keys are pilot names)

All submitted flights for each pilot, including non-scoring flights (i.e. a pilot with
5 flights will have all 5 listed here, even though only the best 3 count).

```json
"Glen Kelley": [
  {
    "Pilot": "Glen Kelley",
    "Date": "2026-04-26",
    "Glider": "JS3-18",
    "Start": "12:54:07",
    "TOC": "02:51:25",
    "H'capped Distance": 155.78,
    "H'capped Speed": 54.53,
    "Score": 1000
  }
]
```

- `Date`: ISO 8601 date string (`YYYY-MM-DD`) — **consistent format throughout**,
  both here and in `scoring_summary`. (Note: original sample used `YYYY/MM/DD` here
  vs `YYYY-MM-DD` in scoring_summary — the contest manager has been asked to
  normalize to `YYYY-MM-DD` everywhere.)
- `Start`: time string `HH:MM:SS` (task start time)
- `TOC`: time string — format should be consistently `HH:MM:SS` (time on course).
  Contest manager has been asked to confirm this is always HH:MM:SS and never MM:SS.
- `H'capped Distance`: float, handicapped distance in status miles
- `H'capped Speed`: float, handicapped speed in miles per hour
- `Score`: integer, this flight's individual point score

### Schema change requests (pending contest manager confirmation)

1. ✅ `Flights of` changed from comma-separated string to array of date strings
2. ✅ Date format normalized to `YYYY-MM-DD` throughout (was `YYYY/MM/DD` in flight
   detail records)
3. ⏳ `TOC` format confirmed as always `HH:MM:SS` (awaiting confirmation)

## Leaderboard page design (HTML rendered by cron script)

Two sections on a single page:

**Section 1 — Standings table**

| Rank | Pilot | Score (best 3) | Scoring Flights |
|------|-------|----------------|-----------------|
| 1 | David Joyce | 2481 | May 12, Jun 16, Jun 24 |
| 2 | Glen Kelley | 1884 | Apr 26, Jun 24 |
...

- Rank computed from score (descending), not from array position
- Scoring flight dates displayed as human-readable (e.g. "Apr 26") and hyperlinked
  to the corresponding row in Section 2
- Ties (equal scores): show same rank, skip next rank number (standard competition
  convention)

**Section 2 — Flight details by pilot**

Collapsible (or simply stacked) per-pilot tables showing all submitted flights,
with scoring flights visually distinguished (bold, highlight, or checkmark column).
Columns: Date, Glider, Start, Time on Course, H'capped Distance, H'capped Speed, Score.

**Footer**

"Last updated: [generated_at formatted as human-readable datetime]"
"Scores computed by WinScore. Best 3 flights count toward season total."

## Implementation plan

### Step 1 — Drupal setup (one-time, manual)

1. Create a new Basic Page node on soargbsc.net titled "Gold Cup Leaderboard"
2. Note the node ID (visible in the URL when editing: `/node/NNN/edit`)
3. Set the text format to "Full HTML" (needed so drush can write HTML into the body)
4. Add the page to the appropriate menu or navigation location
5. Leave the body blank initially — the cron script will populate it

### Step 2 — Cron script (`update_leaderboard.py`)

Location on server: somewhere outside the webroot, e.g. `~/scripts/update_leaderboard.py`

Responsibilities:
- Fetch JSON from the contest manager's published URL
- Validate top-level structure (abort and log if `scoring_summary` or
  `flights_grouped_by_pilot` keys are missing, or if `generated_at` is absent)
- Render HTML (standings table + flight detail tables)
- Call drush to update the Drupal node body
- Log success/failure with timestamp (to a local log file)

The script uses only Python standard library (`urllib.request`, `json`, `subprocess`,
`logging`) — no pip installs required.

Drush call pattern:
```bash
drush --root=/path/to/drupal --uri=https://www.soargbsc.net \
  php-eval "
    \$node = \Drupal\node\Entity\Node::load(NODE_ID);
    \$node->set('body', ['value' => '$html', 'format' => 'full_html']);
    \$node->save();
  "
```

(Exact drush root path and node ID to be confirmed during setup.)

### Step 3 — Cron job registration

Add to the SSH user's crontab (`crontab -e`):

```
# Update Gold Cup leaderboard — runs every hour
0 * * * * /usr/bin/python3 ~/scripts/update_leaderboard.py >> ~/logs/leaderboard.log 2>&1
```

Frequency (hourly shown above) is a placeholder — adjust to match how often the
contest manager realistically updates the JSON. Daily would likely suffice given the
manual WinScore workflow.

## Open questions

1. **JSON publish URL** — where will the contest manager host the JSON file? Options:
   - A file on soargbsc.net itself (simplest, no external dependency)
   - A GitHub repository (version history is a nice bonus)
   - Google Drive or Dropbox public link (works but URLs can be fragile)
   - Ideal: a stable URL that never changes between updates (same URL, content replaced)

2. **TOC format** — confirm `HH:MM:SS` always, never `MM:SS` (awaiting contest manager)

3. **Drush root path** — need exact filesystem path to Drupal root on the host
   (e.g. `/var/www/html` or `/home/gbsc/public_html`) to construct drush commands

4. **Node ID** — assigned when the Basic Page node is created in Step 1

~~5. **Crontab access** — confirm the SSH user can manage their own crontab~~
   ~~(`crontab -e` works without sudo)~~  
   Confirmed.  
   Issue closed.

~~6. **Update frequency** — how often does the contest manager plan to publish a new~~
   ~~JSON file? (Determines cron schedule)~~ 
   At most daily.

## Files in this repository

```
PROJECT_PLAN.md          — this document
scripts/
  update_leaderboard.py  — cron script (to be written)
sample/
  leaderboard_sample.json — sample JSON from contest manager (for development/testing)
```

## Reference

- Gold Cup contest rules: https://www.soargbsc.net/gold_cup_contest
- GBSC website: https://www.soargbsc.net
