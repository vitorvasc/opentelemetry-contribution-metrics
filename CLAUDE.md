# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Guidelines

- **Always document new pipelines**: When creating a new data pipeline or flow, update both `README.md` and this file (`CLAUDE.md`) with the new commands, architecture details, and file references.

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

# Verify setup
make setup-check

# Clean generated data
make clean-lang-contributions
make clean-release-metrics
make clean-merged-prs
```

## Architecture

The project uses a two-stage pipeline: **Node.js for data fetching** → **Python for processing/visualization**.

### Data Flow

1. **Fetch scripts** (`scripts/fetch/*.js`) call GitHub API, output JSON to `data/`
2. **Processing scripts** (`scripts/processing/*_to_csv.py`) convert JSON to accumulated CSV
3. **Plot script** (`scripts/processing/plot.py`) reads CSV + `config.yaml`, displays matplotlib chart

### Three Pipelines

- **Language Contributions**: Tracks individual PRs/issues with `lang:*` labels over time
- **Release Metrics**: Tracks translation lines/pages per monthly release tag (YYYY.MM)
- **Merged PRs**: Tracks total merged PRs across the repository (monthly accumulation)

### Key Files

- `config.yaml` - Plot appearance (colors per language, display options)
- `.env` - GitHub token (required, loaded via `dotenv`)
- `Makefile` - Entry point for all operations

## Environment Variables

- `GITHUB_TOKEN` - Required, set in `.env` file
- `YEAR` - Filter year (default: 2025)
- `LANGS` - Comma-separated language codes (bn,es,fr,ja,pt,ro,uk,zh)
- `TYPE` - Contribution type filter: `prs`, `issues`, or `both`
- `MODE` - Plot mode for merged PRs: `accumulated` (line) or `monthly` (bars)

## Dependencies

- Node.js 18+ with `dotenv`, `node-fetch`
- Python 3.8+ with `matplotlib`, `pandas`, `pyyaml`
