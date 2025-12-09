# Caminhos dos scripts
SCRIPTS_DIR := ./scripts
DATA_DIR := ./data

# Arquivos gerados
JSON=$(DATA_DIR)/lang_contributions.json
CSV=$(DATA_DIR)/lang_accumulated.csv

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

# ---------- TARGETS ----------

# Verificar se .env existe
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy .env.example to .env and set your GITHUB_TOKEN."; \
		exit 1; \
	fi

# Pipeline completo
all: check-env fetch csv plot

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

# Verificar configuração do ambiente
setup-check:
	@bash $(SCRIPTS_DIR)/check_setup.sh

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
	@echo "  make setup-check    - Verifica se o ambiente está configurado"
	@echo ""
	@echo "Setup:"
	@echo "  1. Copie .env.example para .env"
	@echo "  2. Adicione seu GITHUB_TOKEN no arquivo .env"
	@echo ""
	@echo "Idiomas disponíveis: bn, es, fr, ja, pt, ro, uk, zh"
	@echo ""

.PHONY: all fetch csv plot clean help check-env setup-check