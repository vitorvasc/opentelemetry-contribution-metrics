# Caminhos dos scripts
SCRIPTS_DIR := $(dir $(lastword $(MAKEFILE_LIST)))

# Arquivos gerados
JSON=$(SCRIPTS_DIR)/lang_contributions.json
CSV=$(SCRIPTS_DIR)/lang_accumulated.csv

# Comandos principais
NODE=node
PYTHON=python3

# Variáveis externas
# Você deve exportar o token antes de rodar:
#   export GITHUB_TOKEN=xxxx
export GITHUB_TOKEN

# Languages to fetch (comma-separated)
# Available: bn, es, fr, ja, pt, ro, uk, zh
# Default: all languages
# Usage: make fetch LANGS=pt,es
LANGS ?=
export LANGS

# ---------- TARGETS ----------

# Pipeline completo
all: fetch csv plot

# 1) Buscar dados no GitHub via Node
fetch:
	$(NODE) $(SCRIPTS_DIR)/fetch_lang_issues.js
	@echo "✔ JSON gerado em $(JSON)"
	@if [ -n "$(LANGS)" ]; then echo "  Languages: $(LANGS)"; else echo "  Languages: all (bn, es, fr, ja, pt, ro, uk, zh)"; fi

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

# Ajudinha
help:
	@echo ""
	@echo "Targets disponíveis:"
	@echo "  make fetch          - Baixa PRs com labels lang:*"
	@echo "  make fetch LANGS=pt,es  - Baixa PRs apenas para idiomas específicos"
	@echo "  make csv            - Converte JSON → CSV acumulado"
	@echo "  make plot           - Gera gráfico de contribuições"
	@echo "  make all            - Executa fetch + csv + plot"
	@echo "  make clean          - Remove JSON e CSV"
	@echo ""
	@echo "Idiomas disponíveis: bn, es, fr, ja, pt, ro, uk, zh"
	@echo ""