# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Guidelines

- **Always document new pipelines**: When creating a new data pipeline or flow, update both `README.md` and this file (`CLAUDE.md`) with the new commands, architecture details, and file references.
- **Adding a pipeline or chart**: set the pipeline's variables (`<name>.title`, `.fetch`, `.csv`, `.plot`, `.files`) and add its name to `PIPELINES` in the `Makefile`, which generates `fetch-<name>`, `plot-<name>` and `clean-<name>`. Add a chart by appending its name to `CHARTS` and setting `chart.<name>` in the `Makefile` (a chart that re-plots another chart's data also depends on it); `make charts` attempts every chart and fails at the end if any was not written. Cover new logic with tests.

## Project Overview

Visualization tool for tracking OpenTelemetry localization contributions. Fetches data from GitHub API and generates Grafana-style dark-theme plots showing accumulated contributions over time.

## Common Commands

```bash
# Full pipelines (fetch → process → plot)
make fetch-lang-contributions              # PRs + issues by language
make fetch-lang-contributions TYPE=prs     # PRs only
make fetch-release-metrics                 # Release-based metrics
make fetch-merged-prs                      # Total merged PRs (accumulated line chart)
make fetch-merged-prs MODE=monthly         # Total merged PRs (bar chart)

# With filters
make fetch-lang-contributions YEAR=2024 LANGS=pt,es TYPE=prs
make fetch-merged-prs YEAR=2024 MODE=monthly

# Re-process and plot existing data (no API calls; use the same YEAR as the fetch)
make plot-lang-contributions
make plot-release-metrics
make plot-merged-prs MODE=monthly

# Save a chart instead of opening a window
make plot-merged-prs OUTPUT=out/merged-prs.png

# Every chart as a PNG in out/ (fetches, needs GITHUB_TOKEN, headless)
make charts

# Tests and lint
make test                                  # npm test + MPLBACKEND=Agg pytest (PYTHON=venv/bin/python to override)
make lint                                  # Biome, Ruff check + format, ShellCheck
npm test                                   # JS tests only

# Verify setup
make setup-check

# Clean generated data
make clean-lang-contributions
make clean-release-metrics
make clean-merged-prs

# List targets and variables
make help
```

The npm scripts mirror the `fetch-*` and `clean-*` targets but cannot pass `MODE` or `OUTPUT`.

## Architecture

The project uses a two-stage pipeline: **Node.js for data fetching** → **Python for processing/visualization**.

### Data Flow

1. **Fetch scripts** (`scripts/fetch/*.js`) call GitHub API through `scripts/fetch/lib/github.js` (config from env, client with retries and rate-limit handling, search range splitting under the 1000-result cap, `writeJson`, `run`), output JSON to `data/`
2. **Processing scripts** (`scripts/processing/*_to_csv.py`) convert JSON to accumulated CSV, using `common.py` (`load_json`, `write_csv`, `fail`, `to_utc_naive`)
3. **Plot script** (`scripts/processing/plot.py`) reads CSV + `config.yaml`, draws with `plotting.py`, and either displays the chart or saves it with `--output` (`--source {prs,releases,merged}`, `--mode {accumulated,monthly}`)

Paths under `data/` are relative to the cwd, so run everything from the project root; `config.yaml` is resolved from `__file__`.

### Error Behavior

Fetch errors (failed requests, exhausted retries or rate limits, incomplete search results, truncated git tree) exit 1 through `run()` before anything is written. Missing, unreadable or empty data, no records for the `YEAR`/`TYPE`, and invalid `YEAR`/`TYPE` exit 1 through `fail()` in the CSV/plot steps; a fetch that found nothing (e.g. no releases) writes `[]` and is caught there. Keep new code failing loudly; the Makefile relies on it to stop the pipeline.

### Tests

- `tests/js/` - `node --test`, the fetch library and scripts (fetch is stubbed, no network)
- `tests/python/` - pytest, fixtures in `tests/python/fixtures/`; `pytest.ini` puts `scripts/processing` on `pythonpath`
- CI (`.github/workflows/ci.yml`): lint, test-js, test-python, renovate-config, dependency-review; the `ci` aggregator job is the required check
- Charts workflow (`.github/workflows/charts.yml`): monthly (day 2, 06:00 UTC; upstream `YYYY.MM` releases can lag their month by weeks), manual (`year`, `langs` inputs) and on pull requests that edit the workflow (`LANGS=pt`, previous year); runs `make charts` and uploads `out/*.png` + `data/*.csv` as an artifact (90 days), no write-back. Inputs go through `env:`, are normalized (`langs` lowercased, spaces stripped) and validated before `make`; an empty year resolves in that step (scheduled: the year of the month that just ended; pull request: previous year; manual: current year) and is exported through `GITHUB_ENV`. A chart without data (e.g. no release yet for the year) does not stop the others: they are still uploaded, the run ends red, and the job summary lists the charts not written. Token is `secrets.METRICS_TOKEN || secrets.GITHUB_TOKEN`: a full run costs about 1400 core + 160 search requests, over the Actions token's ~1000/hour, so without `METRICS_TOKEN` the fetch waits out hourly resets (180-minute timeout). `METRICS_TOKEN` should be a fine-grained PAT with public read-only access or a classic PAT with no scopes, never `public_repo` (it grants write access)

### Three Pipelines

- **Language Contributions**: Tracks individual PRs/issues with `lang:*` labels over time
- **Release Metrics**: Tracks translation lines/pages per monthly release tag (YYYY.MM)
- **Merged PRs**: Tracks total merged PRs across the repository (monthly accumulation)

### Key Files

- `config.yaml` - Plot appearance (colors per language, display options)
- `.env` - GitHub token, optional when `GITHUB_TOKEN` is in the environment (loaded via `dotenv`; the environment wins)
- `Makefile` - Entry point for all operations; the three pipelines share one set of rules driven by per-pipeline variables
- `out/` - Charts from `make charts` (gitignored, like `data/`)

## Environment Variables

- `GITHUB_TOKEN` - Required for `fetch-*` and `charts`; from the environment or `.env`
- `YEAR` - Year to fetch and plot (default when unset or empty: current year, UTC). Honored by all three fetches and by the release metrics and merged PRs CSV steps, which exit 1 with a hint if the data has no such year, so `plot-*` needs the same `YEAR` as the fetch. The lang contributions CSV step ignores it
- `LANGS` - Comma-separated language codes (bn,es,fr,ja,ko,pl,pt,ro,uk,zh), default all; lang contributions and release metrics fetches
- `TYPE` - Contribution type: `prs`, `issues`, or `both` (default `both`; anything else exits 1). Lang contributions fetch and CSV/plot steps
- `MODE` - Plot mode for merged PRs: `accumulated` (line, default) or `monthly` (bars). Make only; `plot.py` takes `--mode`
- `OUTPUT` - Path of a PNG to write instead of opening a window; passed to `plot.py` as `--output`
- `PYTHON`, `NODE` - Interpreters used by `make` (e.g. `PYTHON=venv/bin/python`)
- `MPLBACKEND=Agg` - Headless matplotlib; `make charts` and `make test` set it

`YEAR`, `LANGS` and `TYPE` are not defaulted in the Makefile: command-line or environment values reach the scripts, which apply the defaults.

## Dependencies

- Node.js `^22.18.0 || >=24.2.0` (`.node-version` pins 24; the fetch scripts guard `main()` with `import.meta.main`) with `dotenv`
- Python 3.11+ (`.python-version` pins 3.12) with `matplotlib`, `pandas`, `pyyaml`; dev: `pytest`, `ruff` (`requirements-dev.txt`)
