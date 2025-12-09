# Caminhos dos scripts
SCRIPTS_DIR := ./scripts
DATA_DIR := ./data

# Arquivos gerados
JSON=$(DATA_DIR)/lang_contributions.json
CSV=$(DATA_DIR)/lang_accumulated.csv
RELEASE_JSON=$(DATA_DIR)/release_metrics.json
RELEASE_CSV=$(DATA_DIR)/release_metrics_accumulated.csv

# Comandos principais
NODE=node
PYTHON=python3

# Variáveis externas
# O GITHUB_TOKEN agora é carregado do arquivo .env
# Você não precisa mais exportar manualmente
# Apenas crie um arquivo .env com: GITHUB_TOKEN=seu_token

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

# ---------- TARGETS ----------

# Verificar se .env existe
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy .env.example to .env and set your GITHUB_TOKEN."; \
		exit 1; \
	fi

# Language Contributions Pipeline
fetch-lang-contributions: check-env
	@echo "Starting language contributions pipeline..."
	$(NODE) $(SCRIPTS_DIR)/fetch_lang_issues.js
	$(PYTHON) $(SCRIPTS_DIR)/lang_contributions_to_csv.py
	$(PYTHON) $(SCRIPTS_DIR)/plot.py
	@echo "✔ Complete!"

# Release Metrics Pipeline
fetch-release-metrics: check-env
	@echo "Starting release metrics pipeline..."
	$(NODE) $(SCRIPTS_DIR)/fetch_release_metrics.js
	$(PYTHON) $(SCRIPTS_DIR)/release_metrics_to_csv.py
	$(PYTHON) $(SCRIPTS_DIR)/plot.py --source=releases
	@echo "✔ Complete!"

# Clean targets
clean-lang-contributions:
	rm -f $(JSON) $(CSV)
	@echo "✔ Language contributions data removed"

clean-release-metrics:
	rm -f $(RELEASE_JSON) $(RELEASE_CSV)
	@echo "✔ Release metrics data removed"

# Verificar configuração do ambiente
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
	@echo "Other:"
	@echo "  make setup-check                           - Verify environment setup"
	@echo "  make help                                  - Show this help"
	@echo ""
	@echo "Parameters:"
	@echo "  YEAR=XXXX    - Filter by year (default: $(YEAR))"
	@echo "  LANGS=xx,yy  - Filter by languages (default: all - bn,es,fr,ja,pt,ro,uk,zh)"
	@echo "  TYPE=xxx     - Filter contribution type: prs, issues, or both (default: both)"
	@echo ""
	@echo "Setup:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Add your GITHUB_TOKEN to the .env file"
	@echo ""

.PHONY: fetch-lang-contributions fetch-release-metrics clean-lang-contributions clean-release-metrics
.PHONY: help check-env setup-check