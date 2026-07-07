#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib import request

LOGGER = logging.getLogger("gold_cup_leaderboard")


class LeaderboardError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Fetch Gold Cup leaderboard JSON and update a Drupal node."
    )
    parser.add_argument(
        "--json-url",
        default=os.environ.get("LEADERBOARD_JSON_URL"),
        help="Public URL of the leaderboard JSON.",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        help="Read leaderboard JSON from a local file instead of fetching a URL.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=script_dir / "leaderboard_state.json",
        help="Path to the state file used to remember the last generated_at value.",
    )
    parser.add_argument(
        "--drupal-root",
        default=os.environ.get("DRUPAL_ROOT"),
        help="Drupal root path for drush.",
    )
    parser.add_argument(
        "--drupal-uri",
        default=os.environ.get("DRUPAL_URI"),
        help="Drupal site URI for drush, such as https://www.soargbsc.net.",
    )
    parser.add_argument(
        "--node-id",
        type=int,
        default=(
            int(os.environ["DRUPAL_NODE_ID"])
            if os.environ.get("DRUPAL_NODE_ID")
            else None
        ),
        help="Drupal node ID to update.",
    )
    parser.add_argument(
        "--drush-bin",
        default=os.environ.get("DRUSH_BIN", "drush"),
        help="Drush executable to invoke.",
    )
    parser.add_argument(
        "--write-html",
        type=Path,
        help="Write the rendered HTML to a local file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and validate, but do not call drush or write the state file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_payload(json_url: str | None, json_file: Path | None) -> dict[str, Any]:
    if json_file is not None:
        LOGGER.info("Loading leaderboard JSON from %s", json_file)
        with json_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    if not json_url:
        raise LeaderboardError("Provide --json-url or --json-file.")

    LOGGER.info("Fetching leaderboard JSON from %s", json_url)
    with request.urlopen(json_url, timeout=30) as response:
        charset = response.headers.get_content_charset("utf-8")
        payload = response.read().decode(charset)
    return json.loads(payload)


def validate_payload(payload: dict[str, Any]) -> None:
    required_keys = {"scoring_summary", "flights_grouped_by_pilot", "generated_at"}
    missing = required_keys.difference(payload)
    if missing:
        raise LeaderboardError(f"Missing top-level keys: {', '.join(sorted(missing))}")

    if not isinstance(payload["scoring_summary"], list):
        raise LeaderboardError("scoring_summary must be a list.")
    if not isinstance(payload["flights_grouped_by_pilot"], dict):
        raise LeaderboardError("flights_grouped_by_pilot must be an object.")
    if not isinstance(payload["generated_at"], str):
        raise LeaderboardError("generated_at must be a string.")

    parse_generated_at(payload["generated_at"])

    for entry in payload["scoring_summary"]:
        validate_summary_entry(entry)

    for pilot, flights in payload["flights_grouped_by_pilot"].items():
        if not isinstance(pilot, str):
            raise LeaderboardError(
                "Pilot names in flights_grouped_by_pilot must be strings."
            )
        if not isinstance(flights, list):
            raise LeaderboardError(f"Flights for {pilot} must be a list.")
        for flight in flights:
            validate_flight_entry(pilot, flight)


def validate_summary_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise LeaderboardError("Each scoring_summary entry must be an object.")

    for key in ("Pilot", "Score (best three)", "Flights of"):
        if key not in entry:
            raise LeaderboardError(f"scoring_summary entry missing {key}.")

    if not isinstance(entry["Pilot"], str):
        raise LeaderboardError("Pilot must be a string in scoring_summary.")
    if not isinstance(entry["Score (best three)"], int):
        raise LeaderboardError("Score (best three) must be an integer.")
    if not isinstance(entry["Flights of"], list):
        raise LeaderboardError("Flights of must be a list.")

    for flight_date in entry["Flights of"]:
        if not isinstance(flight_date, str):
            raise LeaderboardError("Flights of entries must be date strings.")
        parse_iso_date(flight_date)


def validate_flight_entry(pilot: str, flight: Any) -> None:
    if not isinstance(flight, dict):
        raise LeaderboardError(f"Flight entry for {pilot} must be an object.")

    required = [
        "Pilot",
        "Date",
        "Glider",
        "Start",
        "TOC",
        "H'capped Distance",
        "H'capped Speed",
        "Score",
    ]
    for key in required:
        if key not in flight:
            raise LeaderboardError(f"Flight entry for {pilot} missing {key}.")

    if flight["Pilot"] != pilot:
        raise LeaderboardError(f"Flight pilot mismatch for {pilot}.")

    if not isinstance(flight["Glider"], str):
        raise LeaderboardError(f"Glider must be a string for {pilot}.")
    if not isinstance(flight["Score"], int):
        raise LeaderboardError(f"Score must be an integer for {pilot}.")
    if not isinstance(flight["H'capped Distance"], (int, float)):
        raise LeaderboardError(f"H'capped Distance must be numeric for {pilot}.")
    if not isinstance(flight["H'capped Speed"], (int, float)):
        raise LeaderboardError(f"H'capped Speed must be numeric for {pilot}.")

    parse_iso_date(flight["Date"])
    parse_hms(flight["Start"], label=f"Start for {pilot}")
    parse_hms(flight["TOC"], label=f"TOC for {pilot}")


def parse_generated_at(value: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise LeaderboardError(f"generated_at is not valid ISO 8601: {value}") from exc


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise LeaderboardError(f"Invalid ISO date: {value}") from exc


def parse_hms(value: Any, label: str) -> dt.time:
    if not isinstance(value, str):
        raise LeaderboardError(f"{label} must be a string.")
    try:
        return dt.time.fromisoformat(value)
    except ValueError as exc:
        raise LeaderboardError(f"{label} is not in HH:MM:SS format: {value}") from exc


def load_previous_generated_at(state_file: Path) -> str | None:
    if not state_file.exists():
        return None

    with state_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    generated_at = data.get("generated_at")
    return generated_at if isinstance(generated_at, str) else None


def save_generated_at(state_file: Path, generated_at: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w", encoding="utf-8") as handle:
        json.dump({"generated_at": generated_at}, handle, indent=2)
        handle.write("\n")


def compute_ranks(summary: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    ranked: list[tuple[int, dict[str, Any]]] = []
    previous_score: int | None = None
    previous_rank = 0

    for index, entry in enumerate(summary, start=1):
        score = entry["Score (best three)"]
        rank = previous_rank if score == previous_score else index
        ranked.append((rank, entry))
        previous_score = score
        previous_rank = rank

    return ranked


def render_html(payload: dict[str, Any]) -> str:
    summary = payload["scoring_summary"]
    flights_by_pilot = payload["flights_grouped_by_pilot"]
    generated_at = parse_generated_at(payload["generated_at"])

    sections = [
        '<div class="gold-cup-leaderboard">',
        "<style>",
        css_block(),
        "</style>",
        "<section>",
        "<h2>Standings</h2>",
        f"<p>Last updated: {escape_text(format_generated_at(generated_at))}",
        "<br>Best 3 flights count toward score.",
        '<br>Complete rules are on the <A href="https://www.soargbsc.net/gold_cup_contest">Gold Cup Contest page</A></p>',
        '<table class="gold-cup-table standings">',
        "<thead>",
        '<tr><th rowspan="2">Rank</th><th rowspan="2">Pilot</th><th rowspan="2">Score (best 3)</th><th colspan="3">Scoring Flights</th></tr>',
        "<tr><th>1st</th><th>2nd</th><th>3rd</th></tr>",
        "</thead>",
        "<tbody>",
    ]

    for rank, entry in compute_ranks(summary):
        pilot = escape_text(entry["Pilot"])
        score = entry["Score (best three)"]
        flight_dates = sorted(entry["Flights of"])
        flight_cells = "".join(
            (
                f"<td>{make_scoring_link(entry['Pilot'], flight_dates[i])}</td>"
                if i < len(flight_dates)
                else "<td></td>"
            )
            for i in range(3)
        )
        sections.append(
            "<tr>"
            f"<td>{rank}</td>"
            f"<td>{pilot}</td>"
            f"<td>{score}</td>"
            f"{flight_cells}"
            "</tr>"
        )

    sections.extend(
        [
            "</tbody>",
            "</table>",
            "</section>",
            "<section>",
            "<h2>Flight Details</h2>",
            '<table class="gold-cup-table flights">',
            "<thead><tr><th>Pilot</th><th>Scoring</th><th>Date</th><th>Glider</th><th>Start</th><th>Time on Course</th><th>H&#39;capped Distance</th><th>H&#39;capped Speed</th><th>Score</th></tr></thead>",
            "<tbody>",
        ]
    )

    for pilot in sorted(flights_by_pilot, key=str.casefold):
        scoring_dates = scoring_dates_for_pilot(summary, pilot)
        sections.extend(
            render_pilot_rows(pilot, flights_by_pilot[pilot], scoring_dates)
        )

    sections.extend(
        [
            "</tbody>",
            "</table>",
            "</section>",
            '<footer class="gold-cup-footer">',
            "<p>Scores computed by WinScore.",
            "</footer>",
            "</div>",
        ]
    )
    return "\n".join(sections)


def scoring_dates_for_pilot(summary: list[dict[str, Any]], pilot: str) -> set[str]:
    for entry in summary:
        if entry["Pilot"] == pilot:
            return set(entry["Flights of"])
    return set()


def render_pilot_rows(
    pilot: str, flights: list[dict[str, Any]], scoring_dates: set[str]
) -> list[str]:
    lines: list[str] = []

    sorted_flights = sorted(flights, key=lambda item: item["Date"], reverse=True)
    for index, flight in enumerate(sorted_flights):
        is_scoring = flight["Date"] in scoring_dates
        row_class = ' class="scoring-flight"' if is_scoring else ""
        scoring_marker = "Yes" if is_scoring else ""
        anchor = flight_anchor_id(pilot, flight["Date"])
        handicapped_distance = format_decimal(flight["H'capped Distance"])
        handicapped_speed = format_decimal(flight["H'capped Speed"])
        pilot_cell = ""
        if index == 0:
            pilot_cell = (
                f'<td rowspan="{len(sorted_flights)}">{escape_text(pilot)}</td>'
            )
        lines.append(
            f'<tr id="{anchor}"{row_class}>'
            f"{pilot_cell}"
            f"<td>{scoring_marker}</td>"
            f"<td>{escape_text(format_date(flight['Date']))}</td>"
            f"<td>{escape_text(flight['Glider'])}</td>"
            f"<td>{escape_text(flight['Start'])}</td>"
            f"<td>{escape_text(flight['TOC'])}</td>"
            f"<td>{handicapped_distance}</td>"
            f"<td>{handicapped_speed}</td>"
            f"<td>{flight['Score']}</td>"
            "</tr>"
        )
    return lines


def format_date(value: str) -> str:
    return parse_iso_date(value).strftime("%b %d, %Y")


def format_generated_at(value: dt.datetime) -> str:
    return value.strftime("%b %d, %Y %H:%M")


def format_decimal(value: int | float) -> str:
    return f"{value:.2f}"


def make_scoring_link(pilot: str, flight_date: str) -> str:
    label = format_short_date(flight_date)
    anchor = flight_anchor_id(pilot, flight_date)
    return f'<a href="#{anchor}">{escape_text(label)}</a>'


def format_short_date(value: str) -> str:
    parsed = parse_iso_date(value)
    return parsed.strftime("%b %d").replace(" 0", " ")


def flight_anchor_id(pilot: str, flight_date: str) -> str:
    pilot_slug = "-".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in pilot).split()
    )
    return f"flight-{pilot_slug}-{flight_date}"


def escape_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def css_block() -> str:
    return """\
.gold-cup-leaderboard {
  font-family: Arial, sans-serif;
  line-height: 1.5;
}

.gold-cup-table {
  border-collapse: collapse;
  margin-bottom: 1.5rem;
    width: auto;
}

.gold-cup-table th,
.gold-cup-table td {
  border: 1px solid #cfd7df;
  padding: 0.5rem 0.65rem;
  text-align: left;
}

.gold-cup-table thead {
  background: #eef3f7;
}

.scoring-flight {
  background: #f4fbef;
  font-weight: 600;
}

.gold-cup-footer {
  border-top: 1px solid #cfd7df;
  margin-top: 2rem;
  padding-top: 1rem;
}
"""


def write_html(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def update_drupal_node(
    *,
    drush_bin: str,
    drupal_root: str,
    drupal_uri: str,
    node_id: int,
    html_body: str,
) -> None:
    payload = json.dumps({"value": html_body, "format": "full_html"})
    php = (
        "$body = json_decode(getenv('LEADERBOARD_BODY'), true);"
        f"$node = \\Drupal\\node\\Entity\\Node::load({node_id});"
        "if (!$node) { fwrite(STDERR, 'Node not found\\n'); exit(1); }"
        "$node->set('body', $body);"
        "$node->save();"
    )

    env = os.environ.copy()
    env["LEADERBOARD_BODY"] = payload

    command = [
        drush_bin,
        f"--root={drupal_root}",
        f"--uri={drupal_uri}",
        "php-eval",
        php,
    ]
    LOGGER.info("Updating Drupal node %s with drush", node_id)
    subprocess.run(command, check=True, env=env)


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    try:
        payload = load_payload(args.json_url, args.json_file)
        validate_payload(payload)

        previous_generated_at = load_previous_generated_at(args.state_file)
        current_generated_at = payload["generated_at"]

        if previous_generated_at == current_generated_at:
            LOGGER.info(
                "No update needed; generated_at is unchanged at %s",
                current_generated_at,
            )
            return 0

        html_output = render_html(payload)

        if args.write_html:
            write_html(args.write_html, html_output)
            LOGGER.info("Wrote rendered HTML to %s", args.write_html)

        if args.dry_run:
            LOGGER.info("Dry run complete; Drupal was not updated.")
            return 0

        missing = []
        if not args.drupal_root:
            missing.append("--drupal-root or DRUPAL_ROOT")
        if not args.drupal_uri:
            missing.append("--drupal-uri or DRUPAL_URI")
        if args.node_id is None:
            missing.append("--node-id or DRUPAL_NODE_ID")
        if missing:
            raise LeaderboardError(
                "Missing Drupal configuration: " + ", ".join(missing)
            )

        update_drupal_node(
            drush_bin=args.drush_bin,
            drupal_root=args.drupal_root,
            drupal_uri=args.drupal_uri,
            node_id=args.node_id,
            html_body=html_output,
        )
        save_generated_at(args.state_file, current_generated_at)
        LOGGER.info("Leaderboard update completed successfully.")
        return 0
    except (
        LeaderboardError,
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        LOGGER.error("Leaderboard update failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
