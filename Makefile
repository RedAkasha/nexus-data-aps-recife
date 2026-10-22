# Atalhos (Linux/macOS/WSL). No Windows sem make, use os comandos do README.
PY ?= python
CENARIO ?= base

instalar:
	$(PY) -m pip install -e ".[tudo]"
demo:
	$(PY) -m aps_sintetico tudo --cenario demo --sem-banco --sem-mlflow
gerar:
	$(PY) -m aps_sintetico gerar --cenario $(CENARIO)
carregar:
	$(PY) -m aps_sintetico carregar --cenario $(CENARIO)
validar:
	$(PY) -m aps_sintetico validar --cenario $(CENARIO)
tudo:
	$(PY) -m aps_sintetico tudo --cenario $(CENARIO)
painel:
	$(PY) -m aps_sintetico painel --cenario $(CENARIO)
testes:
	$(PY) -m pytest
infra:
	docker compose up -d
.PHONY: instalar demo gerar carregar validar tudo painel testes infra
