# Script paths
SCRIPTS_DIR := ./scripts
FETCH_DIR := ./scripts/fetch
PROCESSING_DIR := ./scripts/processing
DATA_DIR := ./data

# Main commands
NODE=node
PYTHON=python3

# External variables
# GITHUB_TOKEN is now loaded from .env file
# You don't need to export it manually anymore
# Just create a .env file with: GITHUB_TOKEN=your_token

# Languages to fetch (comma-separated)
# Available: bn, es, fr, ja, pt, ro, uk, zh
# Default: all languages
# Usage: make fetch LANGS=pt,es
LANGS ?=
export LANGS

# Year to filter data (default: current year)
# Usage: make fetch-lang-contributions YEAR=2024
YEAR ?= 2025
export YEAR

# Contribution type filter (prs, issues, or both)
# Usage: make fetch-lang-contributions TYPE=prs
TYPE ?=
export TYPE

# Plot mode for merged PRs (accumulated or monthly)
# Usage: make fetch-merged-prs MODE=monthly
MODE ?= accumulated
export MODE

# ---------- TARGETS ----------

# Default target: show help
.DEFAULT_GOAL := help

# Check if .env exists
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy .env.example to .env and set your GITHUB_TOKEN."; \
		exit 1; \
	fi

# Pipelines
#
# Every pipeline gets fetch-NAME, plot-NAME and clean-NAME from the shared
# rules below. Per pipeline:
#   title  name used in messages
#   fetch  Node script that writes the raw JSON
#   csv    Python script that turns the JSON into the accumulated CSV
#   plot   extra plot.py flags
#   files  generated files removed by clean-NAME
PIPELINES := lang-contributions release-metrics merged-prs

lang-contributions.title := language contributions
lang-contributions.fetch := fetch_lang_issues.js
lang-contributions.csv := lang_contributions_to_csv.py
lang-contributions.plot :=
lang-contributions.files := $(DATA_DIR)/lang_contributions.json $(DATA_DIR)/lang_accumulated.csv

release-metrics.title := release metrics
release-metrics.fetch := fetch_release_metrics.js
release-metrics.csv := release_metrics_to_csv.py
release-metrics.plot := --source=releases
release-metrics.files := $(DATA_DIR)/release_metrics.json $(DATA_DIR)/release_metrics_accumulated.csv

merged-prs.title := merged PRs
merged-prs.fetch := fetch_merged_prs.js
merged-prs.csv := merged_prs_to_csv.py
merged-prs.plot = --source=merged --mode=$(MODE)
merged-prs.files := $(DATA_DIR)/merged_prs.json $(DATA_DIR)/merged_prs_accumulated.csv

FETCH_TARGETS := $(addprefix fetch-,$(PIPELINES))
PLOT_TARGETS := $(addprefix plot-,$(PIPELINES))
CLEAN_TARGETS := $(addprefix clean-,$(PIPELINES))

# Convert the fetched JSON to CSV, then draw it ($(1) is the pipeline name)
define process_and_plot
$(PYTHON) $(PROCESSING_DIR)/$($(1).csv)
$(PYTHON) $(PROCESSING_DIR)/plot.py $($(1).plot)
endef

$(FETCH_TARGETS): fetch-%: check-env
	@echo "Starting $($*.title) pipeline..."
	$(NODE) $(FETCH_DIR)/$($*.fetch)
	$(call process_and_plot,$*)
	@echo "✔ Complete!"

# Plot-only targets (skip fetching, use existing data)
$(PLOT_TARGETS): plot-%:
	@echo "Plotting existing $($*.title) data..."
	$(call process_and_plot,$*)
	@echo "✔ Complete!"

$(CLEAN_TARGETS): clean-%:
	rm -f $($*.files)
	@echo "✔ Removed $($*.title) data"

# Verify environment configuration
setup-check:
	@bash $(SCRIPTS_DIR)/check_setup.sh

# Help
help:
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "  OpenTelemetry Contribution Metrics - Available Commands"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "Language Contributions Pipeline:"
	@echo "  make fetch-lang-contributions              - Fetch, process, and plot (PRs + issues)"
	@echo "  make fetch-lang-contributions TYPE=prs     - Same, but only PRs"
	@echo "  make fetch-lang-contributions TYPE=issues  - Same, but only issues"
	@echo "  make fetch-lang-contributions YEAR=2024    - Filter by year"
	@echo "  make fetch-lang-contributions LANGS=pt,es  - Filter by languages"
	@echo "  make clean-lang-contributions              - Remove data files"
	@echo ""
	@echo "Release Metrics Pipeline:"
	@echo "  make fetch-release-metrics                 - Fetch, process, and plot release metrics"
	@echo "  make fetch-release-metrics YEAR=2024       - Filter by year"
	@echo "  make clean-release-metrics                 - Remove data files"
	@echo ""
	@echo "Merged PRs Pipeline:"
	@echo "  make fetch-merged-prs                      - Fetch, process, and plot total merged PRs (accumulated)"
	@echo "  make fetch-merged-prs YEAR=2024            - Filter by year"
	@echo "  make fetch-merged-prs MODE=monthly         - Month-over-month bar chart"
	@echo "  make fetch-merged-prs YEAR=2024 MODE=monthly - Combined filters"
	@echo "  make clean-merged-prs                      - Remove data files"
	@echo ""
	@echo "Plot Only (use existing data, no API calls):"
	@echo "  make plot-lang-contributions               - Re-plot language contributions"
	@echo "  make plot-release-metrics                  - Re-plot release metrics"
	@echo "  make plot-merged-prs                       - Re-plot merged PRs"
	@echo "  make plot-merged-prs MODE=monthly          - Re-plot as bar chart"
	@echo ""
	@echo "Other:"
	@echo "  make setup-check                           - Verify environment setup"
	@echo "  make help                                  - Show this help"
	@echo ""
	@echo "Parameters:"
	@echo "  YEAR=XXXX    - Filter by year (default: $(YEAR))"
	@echo "  LANGS=xx,yy  - Filter by languages (default: all - bn,es,fr,ja,pt,ro,uk,zh)"
	@echo "  TYPE=xxx     - Filter contribution type: prs, issues, or both (default: both)"
	@echo "  MODE=xxx     - Plot mode for merged PRs: accumulated or monthly (default: accumulated)"
	@echo ""
	@echo "Setup:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Add your GITHUB_TOKEN to the .env file"
	@echo ""

.PHONY: $(FETCH_TARGETS) $(PLOT_TARGETS) $(CLEAN_TARGETS)
.PHONY: help check-env setup-check
