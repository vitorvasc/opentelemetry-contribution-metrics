# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Visualization tool for tracking OpenTelemetry localization contributions. Fetches data from GitHub API and generates Grafana-style dark-theme plots showing accumulated contributions over time.

## Common Commands

```bash
# Full pipelines (fetch → process → plot)
make fetch-lang-contributions              # PRs + issues by language
make fetch-lang-contributions TYPE=prs     # PRs only
make fetch-release-metrics                 # Release-based metrics

# With filters
make fetch-lang-contributions YEAR=2024 LANGS=pt,es TYPE=prs

# Verify setup
make setup-check

# Clean generated data
make clean-lang-contributions
make clean-release-metrics
```

## Architecture

The project uses a two-stage pipeline: **Node.js for data fetching** → **Python for processing/visualization**.

### Data Flow

1. **Fetch scripts** (`scripts/fetch/*.js`) call GitHub API, output JSON to `data/`
2. **Processing scripts** (`scripts/processing/*_to_csv.py`) convert JSON to accumulated CSV
3. **Plot script** (`scripts/processing/plot.py`) reads CSV + `config.yaml`, displays matplotlib chart

### Two Pipelines

- **Language Contributions**: Tracks individual PRs/issues with `lang:*` labels over time
- **Release Metrics**: Tracks translation lines/pages per monthly release tag (YYYY.MM)

### Key Files

- `config.yaml` - Plot appearance (colors per language, display options)
- `.env` - GitHub token (required, loaded via `dotenv`)
- `Makefile` - Entry point for all operations

## Environment Variables

- `GITHUB_TOKEN` - Required, set in `.env` file
- `YEAR` - Filter year (default: 2025)
- `LANGS` - Comma-separated language codes (bn,es,fr,ja,pt,ro,uk,zh)
- `TYPE` - Contribution type filter: `prs`, `issues`, or `both`

## Dependencies

- Node.js 18+ with `dotenv`, `node-fetch`
- Python 3.8+ with `matplotlib`, `pandas`, `pyyaml`
