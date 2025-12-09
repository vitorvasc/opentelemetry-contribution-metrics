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
# Usage: make fetch YEAR=2024
YEAR ?= 2025
export YEAR

# ---------- TARGETS ----------

# Verificar se .env existe
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy .env.example to .env and set your GITHUB_TOKEN."; \
		exit 1; \
	fi

# 1) Buscar dados no GitHub via Node
fetch:
	$(NODE) $(SCRIPTS_DIR)/fetch_lang_issues.js
	@echo "✔ JSON gerado em $(JSON)"
	@if [ -n "$(LANGS)" ]; then echo "  Languages: $(LANGS)"; else echo "  Languages: all (bn, es, fr, ja, pt, ro, uk, zh)"; fi
	@echo "  Year: $(YEAR)"

# 2) Converter JSON em CSV acumulado via Python
csv:
	$(PYTHON) $(SCRIPTS_DIR)/lang_contributions_to_csv.py
	@echo "✔ CSV gerado em $(CSV)"

# 3) Gerar o gráfico via Python (matplotlib)
plot:
	$(PYTHON) $(SCRIPTS_DIR)/plot.py
	@echo "✔ Gráfico exibido"

# Limpar arquivos gerados
clean:
	rm -f $(JSON) $(CSV)
	@echo "✔ Arquivos removidos"

# Limpar arquivos de releases
clean-releases:
	rm -f $(RELEASE_JSON) $(RELEASE_CSV)
	@echo "✔ Arquivos de releases removidos"

# ---------- RELEASE-BASED METRICS ----------

# 1) Buscar métricas por release
fetch-releases:
	$(NODE) $(SCRIPTS_DIR)/fetch_release_metrics.js
	@echo "✔ Release JSON gerado em $(RELEASE_JSON)"
	@if [ -n "$(LANGS)" ]; then echo "  Languages: $(LANGS)"; else echo "  Languages: all (bn, es, fr, ja, pt, ro, uk, zh)"; fi
	@echo "  Year: $(YEAR)"

# 2) Converter release JSON em CSV acumulado
csv-releases:
	$(PYTHON) $(SCRIPTS_DIR)/release_metrics_to_csv.py
	@echo "✔ Release CSV gerado em $(RELEASE_CSV)"

# 3) Gerar gráfico de releases
plot-releases:
	$(PYTHON) $(SCRIPTS_DIR)/plot.py --source=releases
	@echo "✔ Gráfico de releases exibido"

# Pipeline completo de releases
releases: check-env fetch-releases csv-releases plot-releases

# ---------- END RELEASE METRICS ----------

# Verificar configuração do ambiente
setup-check:
	@bash $(SCRIPTS_DIR)/check_setup.sh

# Ajudinha
help:
	@echo ""
	@echo "Targets disponíveis (PR-based metrics):"
	@echo "  make fetch          - Baixa PRs com labels lang:* (ano atual)"
	@echo "  make fetch LANGS=pt,es  - Baixa PRs apenas para idiomas específicos"
	@echo "  make fetch YEAR=2024    - Baixa PRs de um ano específico"
	@echo "  make csv            - Converte JSON → CSV acumulado"
	@echo "  make plot           - Gera gráfico de contribuições"
	@echo "  make clean          - Remove JSON e CSV"
	@echo ""
	@echo "Targets de release (métricas mensais por release):"
	@echo "  make fetch-releases - Baixa métricas por release mensal (YYYY.MM) do ano atual"
	@echo "  make fetch-releases YEAR=2024  - Filtra releases de um ano específico"
	@echo "  make csv-releases   - Converte release JSON → CSV"
	@echo "  make plot-releases  - Gera gráfico de métricas por release"
	@echo "  make releases       - Executa fetch-releases + csv-releases + plot-releases"
	@echo "  make clean-releases - Remove arquivos de releases"
	@echo ""
	@echo "Outros:"
	@echo "  make setup-check    - Verifica se o ambiente está configurado"
	@echo "  make help           - Mostra esta ajuda"
	@echo ""
	@echo "Setup:"
	@echo "  1. Copie .env.example para .env"
	@echo "  2. Adicione seu GITHUB_TOKEN no arquivo .env"
	@echo ""
	@echo "Idiomas disponíveis: bn, es, fr, ja, pt, ro, uk, zh"
	@echo "Ano padrão: $(YEAR) (pode ser alterado com YEAR=XXXX)"
	@echo ""

.PHONY: fetch csv plot clean help check-env setup-check
.PHONY: fetch-releases csv-releases plot-releases releases clean-releases