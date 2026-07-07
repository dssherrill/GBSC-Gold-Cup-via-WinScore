# Drupal Leaderboard Update Transport Design

## Purpose

Document how rendered leaderboard HTML is transferred from the Python updater to Drush,
why this mechanism was chosen, and what practical size limits apply.

## Current implementation

The updater script renders HTML and calls Drush with inline PHP.

Flow:

1. Python renders HTML for the leaderboard page body.
2. Python wraps body data as JSON:
   - `{"value": "<rendered html>", "format": "full_html"}`
3. Python stores this JSON in environment variable `LEADERBOARD_BODY`.
4. Python runs Drush `php-eval`.
5. PHP reads the env var (`getenv`), decodes JSON (`json_decode`), and writes `$node->set('body', $body)`.

This avoids command-line escaping problems for large HTML content and keeps the Drupal write
path inside Drupal entity APIs.

## Why this is reasonable

- No direct SQL writes.
- Uses Drupal entity save path (expected behavior for field updates).
- No additional Drupal modules or external services.
- No temporary files required for normal operation.
- Works with existing cron + Drush operational model.

## Size limit considerations (Linux)

On Linux, process launch uses `execve`, which applies a limit to the combined size of:

- all command-line arguments (`argv`)
- all environment variables (`envp`)

This is commonly near 2 MB total (`ARG_MAX` often 2,097,152 bytes), but exact value can vary
by host and runtime context.

Important notes:

- There is usually no tiny per-variable limit; the practical limit is the total size budget.
- Existing environment variables consume part of this budget.
- If budget is exceeded, process launch fails (commonly seen as "argument list too long").

## Project-specific sizing assessment

Current rendered leaderboard HTML size is approximately 7 KB at mid-season.

Given current season expectations (fewer flights in remaining period), payload growth risk is
low for this season, and the env-var transport is acceptable.

## Operational guardrails

- Keep current env-var transport unless payload size or errors indicate pressure.
- If payload approaches large sizes (for example, hundreds of KB), migrate to file handoff.
- If Drush launch errors indicate size issues, switch immediately to file handoff pattern.

## Alternative transport patterns

### A. Temporary file handoff (preferred fallback)

1. Python writes body JSON to a temporary file.
2. Python passes file path to Drush (arg or env var).
3. PHP reads file contents and updates node body.

Pros:
- Avoids env/argv size pressure.
- Easy to inspect/debug.

Cons:
- Requires temp-file lifecycle management.

### B. Base64 in argument/env

Encode/decode payload with base64.

Pros:
- Simple and self-contained.

Cons:
- Does not eliminate size limits.
- Less readable and harder to debug.

### C. Drupal HTTP API update

Update node body via REST/JSON:API from Python.

Pros:
- No shell/Drush dependency for writes.

Cons:
- Requires auth/token/permission setup and more operational complexity.

## Decision

For the current season, retain env-var handoff (`LEADERBOARD_BODY`) as implemented.

Revisit only if:

- payload growth materially increases,
- host-specific limits are hit, or
- operational errors indicate env/argv budget pressure.
