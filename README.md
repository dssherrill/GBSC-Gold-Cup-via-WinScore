# GBSC Gold Cup via WinScore

Generate and update Gold Cup leaderboard outputs from WinScore-style JSON data.

## Quick Start

- Activate your Python environment.
- Run a local validation/dry run:

```powershell
python .\scripts\update_leaderboard.py --json-file .\data\leaderboard_sample.json --dry-run --write-html .\data\leaderboard_sample.html
```

## Repository Layout

- `scripts/update_leaderboard.py` - leaderboard update script.
- `data/` - sample and generated leaderboard files.
- `docs/` - deployment and project documentation.
