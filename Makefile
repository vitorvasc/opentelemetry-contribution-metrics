# Script paths
SCRIPTS_DIR := ./scripts
FETCH_DIR := ./scripts/fetch
PROCESSING_DIR := ./scripts/processing
DATA_DIR := ./data

# Main commands (override to use a virtualenv, e.g. PYTHON=.venv/bin/python)
NODE ?= node
PYTHON ?= python3

# Variables read by the scripts, never defaulted here
# GITHUB_TOKEN comes from the environment or from .env (loaded by dotenv).
# YEAR, LANGS and TYPE reach the scripts straight from the command line
# (make fetch-lang-contributions YEAR=2024) or the environment. Unset or empty
# means the script default: current UTC year, all languages, PRs and issues.
#   YEAR   four-digit year to fetch and plot (the PR flow fetch is all-time:
#          there YEAR only picks the months drawn)
#   LANGS  comma-separated language codes (bn,es,fr,ja,ko,pl,pt,ro,uk,zh)
#   TYPE   prs, issues or both (lang contributions only)
#   CLONE_DIR  where fetch-drift keeps its opentelemetry.io clone
#          (default data/.cache/opentelemetry.io)

# Plot mode for merged PRs (accumulated or monthly)
# Usage: make fetch-merged-prs MODE=monthly
MODE ?= accumulated

# Save the chart to this file instead of opening a window
# Usage: make plot-merged-prs OUTPUT=out/merged.png
OUTPUT ?=
PLOT_OUTPUT = $(if $(OUTPUT),--output $(OUTPUT))

# ---------- TARGETS ----------

# Default target: show help
.DEFAULT_GOAL := help

# The token may come from the environment or from a .env file
check-env:
	@if [ -z "$$GITHUB_TOKEN" ] && ! grep -qs '^GITHUB_TOKEN=.' .env; then \
		echo "Error: GITHUB_TOKEN is not set. Export it, or copy .env.example to .env and set it there."; \
		exit 1; \
	fi

# Pipelines
#
# Every pipeline gets fetch-NAME, plot-NAME and clean-NAME from the shared
# rules below. Per pipeline:
#   title  name used in messages
#   fetch  Node script that writes the raw JSON
#   csv    Python script (with its flags) that turns the JSON into the accumulated CSV
#   plot   extra plot.py flags
#   files  generated files removed by clean-NAME
PIPELINES := lang-contributions release-metrics merged-prs coverage pr-flow drift
# Pipelines that clone the public repository instead of calling the GitHub
# API, so their fetch needs no token
TOKENLESS_PIPELINES := drift

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

coverage.title := translation coverage snapshot
coverage.fetch := fetch_coverage.js
coverage.csv := coverage_to_csv.py
coverage.plot := --source=coverage-snapshot
coverage.files := $(DATA_DIR)/coverage_snapshot.json $(DATA_DIR)/coverage_snapshot.csv

pr-flow.title := PR flow
pr-flow.fetch := fetch_pr_flow.js
pr-flow.csv := pr_flow_to_csv.py --only=time-to-merge
pr-flow.plot := --source=time-to-merge
pr-flow.files := $(DATA_DIR)/pr_flow.json $(DATA_DIR)/pr_flow_time_to_merge.csv $(DATA_DIR)/pr_flow_backlog.csv $(DATA_DIR)/pr_flow_contributors.csv $(DATA_DIR)/pr_flow_contributors_year.csv

drift.title := translation drift
drift.fetch := fetch_drift.js
drift.csv := drift_to_csv.py
drift.plot := --source=drift
drift.files := $(DATA_DIR)/drift.json $(DATA_DIR)/drift.csv

FETCH_TARGETS := $(addprefix fetch-,$(PIPELINES))
PLOT_TARGETS := $(addprefix plot-,$(PIPELINES))
CLEAN_TARGETS := $(addprefix clean-,$(PIPELINES))

# Convert the fetched JSON to CSV, then draw it ($(1) is the pipeline name)
define process_and_plot
$(PYTHON) $(PROCESSING_DIR)/$($(1).csv)
$(PYTHON) $(PROCESSING_DIR)/plot.py $(strip $($(1).plot) $(PLOT_OUTPUT))
endef

$(FETCH_TARGETS): fetch-%:
	@echo "Starting $($*.title) pipeline..."
	$(NODE) $(FETCH_DIR)/$($*.fetch)
	$(call process_and_plot,$*)
	@echo "✔ Complete!"

$(addprefix fetch-,$(filter-out $(TOKENLESS_PIPELINES),$(PIPELINES))): check-env

# Plot-only targets (skip fetching, use existing data)
$(PLOT_TARGETS): plot-%:
	@echo "Plotting existing $($*.title) data..."
	$(call process_and_plot,$*)
	@echo "✔ Complete!"

$(CLEAN_TARGETS): clean-%:
	rm -f $($*.files)
	@echo "✔ Removed $($*.title) data"

# clean-drift keeps the clone, so the next fetch-drift only updates it. This
# removes it, and only when fetch-drift made it: fetch_drift.js marks its
# clones with this git config key
DRIFT_CLONE_DIR = $(or $(CLONE_DIR),$(DATA_DIR)/.cache/opentelemetry.io)
DRIFT_CLONE_MARKER := contribution-metrics.cache

clean-drift-cache: ## Remove the opentelemetry.io clone kept by fetch-drift
	@dir='$(DRIFT_CLONE_DIR)'; \
	if [ ! -e "$$dir" ]; then \
		echo "✔ No drift clone at $$dir"; \
	elif [ "$$(git -C "$$dir" rev-parse --show-toplevel 2>/dev/null)" = "$$(cd "$$dir" && pwd -P)" ] && \
		[ "$$(git -C "$$dir" config --local --get $(DRIFT_CLONE_MARKER))" = true ]; then \
		rm -rf "$$dir" && echo "✔ Removed the drift clone at $$dir"; \
	else \
		echo "Error: $$dir is not a clone made by fetch-drift, so it was not removed" >&2; \
		exit 1; \
	fi

# The coverage history is drawn from the release metrics data, so it has no
# fetch or clean of its own: fetch-release-metrics provides the data
coverage-history.title := translation coverage history
coverage-history.csv := release_metrics_to_csv.py
coverage-history.plot := --source=coverage

plot-coverage-history: ## Plot the coverage of each release from the fetched release metrics
	@echo "Plotting existing $(coverage-history.title) data..."
	$(call process_and_plot,coverage-history)
	@echo "✔ Complete!"

# The PR backlog is drawn from the PR flow data, so it has no fetch or clean of
# its own: fetch-pr-flow provides the data (and draws the time to merge). Each
# plot converts only its own CSV, so one without data does not stop the other
pr-backlog.title := open PR backlog
pr-backlog.csv := pr_flow_to_csv.py --only=backlog
pr-backlog.plot := --source=backlog

plot-pr-backlog: ## Plot the PRs open at each month end from the fetched PR flow data
	@echo "Plotting existing $(pr-backlog.title) data..."
	$(call process_and_plot,pr-backlog)
	@echo "✔ Complete!"

# The contributor charts are drawn from the PR flow data too, with no fetch or
# clean of their own (clean-pr-flow removes their CSVs). One conversion writes
# the monthly CSV both charts read and the yearly summary, so each plot runs it
contributors.title := unique contributors
contributors.csv := contributors_to_csv.py
contributors.plot := --source=contributors

new-contributors.title := new contributors
new-contributors.csv := contributors_to_csv.py
new-contributors.plot := --source=new-contributors

plot-contributors: ## Plot the unique contributors of each month from the fetched PR flow data
	@echo "Plotting existing $(contributors.title) data..."
	$(call process_and_plot,contributors)
	@echo "✔ Complete!"

plot-new-contributors: ## Plot the new contributors of each month from the fetched PR flow data
	@echo "Plotting existing $(new-contributors.title) data..."
	$(call process_and_plot,new-contributors)
	@echo "✔ Complete!"

# Every chart the project draws, written headless as a PNG under $(OUT_DIR).
# Per chart:
#   chart.NAME  the pipeline target (and variables) that draws $(OUT_DIR)/NAME.png
# Add a chart: append its name to CHARTS and set chart.NAME. Fetch a dataset
# once with fetch-NAME, then re-plot it with plot-NAME for any further chart of
# the same data (and make that chart depend on the one that fetched it, unless
# the charts can fail independently: then all depend on a fetch-only target, as
# the PR flow charts do on pr-flow-data).
OUT_DIR := out
HEADLESS := MPLBACKEND=Agg

CHARTS := lang-contributions release-metrics merged-prs-accumulated merged-prs-monthly coverage-history coverage-snapshot time-to-merge backlog contributors new-contributors drift
chart.lang-contributions := fetch-lang-contributions
chart.release-metrics := fetch-release-metrics
chart.merged-prs-accumulated := fetch-merged-prs MODE=accumulated
chart.merged-prs-monthly := plot-merged-prs MODE=monthly
chart.coverage-history := plot-coverage-history
chart.coverage-snapshot := fetch-coverage
chart.time-to-merge := plot-pr-flow
chart.backlog := plot-pr-backlog
chart.contributors := plot-contributors
chart.new-contributors := plot-new-contributors
chart.drift := fetch-drift
CHART_TARGETS := $(addprefix chart-,$(CHARTS))

chart-merged-prs-monthly: chart-merged-prs-accumulated
chart-coverage-history: chart-release-metrics
chart-time-to-merge chart-backlog chart-contributors chart-new-contributors: pr-flow-data

# One fetch feeds every PR flow chart. It is its own step so that a year with
# no merges still charts the backlog, and the other way around
pr-flow-data: check-env
	$(NODE) $(FETCH_DIR)/$(pr-flow.fetch)

# A stale chart is removed first, so a PNG in $(OUT_DIR) is always from this run
$(CHART_TARGETS): chart-%:
	@rm -f $(OUT_DIR)/$*.png
	$(HEADLESS) $(MAKE) $(chart.$*) OUTPUT=$(OUT_DIR)/$*.png

# --keep-going tries every chart even when one fails (for example a year with
# no releases yet), then the target fails and names the charts not written
charts: check-env ## Fetch every dataset and write all charts to out/
	@$(MAKE) --keep-going $(CHART_TARGETS) || { \
		for chart in $(CHARTS); do \
			[ -f $(OUT_DIR)/$$chart.png ] || echo "Error: chart $$chart was not written" >&2; \
		done; \
		exit 1; \
	}
	@echo "✔ Charts written to $(OUT_DIR)/"

# Names of the charts, for scripts that check which ones were written
list-charts:
	@echo $(CHARTS)

test: ## Run the JavaScript and Python tests
	npm test
	MPLBACKEND=Agg $(PYTHON) -m pytest

lint: ## Run Biome, Ruff and ShellCheck
	npm run lint
	ruff check .
	ruff format --check .
	shellcheck scripts/check_setup.sh

setup-check: ## Verify Node.js, Python, token and dependencies
	@bash $(SCRIPTS_DIR)/check_setup.sh

help: ## Show this help
	@echo "OpenTelemetry Contribution Metrics"
	@echo ""
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Pipelines (NAME: $(PIPELINES))"
	@echo "  fetch-NAME   Fetch from GitHub, convert to CSV and plot (needs GITHUB_TOKEN, except drift)"
	@echo "  plot-NAME    Convert and plot the data already fetched (no API calls)"
	@echo "  clean-NAME   Remove the generated data files"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables:"
	@echo "  GITHUB_TOKEN  Token for the GitHub API, from the environment or .env"
	@echo "  YEAR=XXXX     Year to fetch and plot (default: current year, UTC; PR flow fetches all time)"
	@echo "  LANGS=xx,yy   Languages to fetch (default: all of bn,es,fr,ja,ko,pl,pt,ro,uk,zh)"
	@echo "  TYPE=xxx      prs, issues or both (default: both, lang contributions only)"
	@echo "  MODE=xxx      Merged PRs chart: accumulated or monthly (default: accumulated)"
	@echo "  OUTPUT=PATH   Save the chart to PATH instead of opening a window"
	@echo "  CLONE_DIR=PATH  Clone kept by fetch-drift (default: data/.cache/opentelemetry.io)"
	@echo ""
	@echo "Examples:"
	@echo "  make fetch-lang-contributions YEAR=2024 LANGS=pt,es TYPE=prs"
	@echo "  make fetch-merged-prs MODE=monthly"
	@echo "  make plot-merged-prs OUTPUT=out/merged-prs.png"

.PHONY: $(FETCH_TARGETS) $(PLOT_TARGETS) $(CLEAN_TARGETS) plot-coverage-history plot-pr-backlog pr-flow-data
.PHONY: plot-contributors plot-new-contributors clean-drift-cache
.PHONY: $(CHART_TARGETS) charts list-charts test lint help check-env setup-check
