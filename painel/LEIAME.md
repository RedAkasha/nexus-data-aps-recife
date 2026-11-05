# Painel Nexus Data – como usar

Copie esta pasta `painel/` para dentro do repositório (substitui o `painel/app.py` antigo).

1. Gere os dados: `python -m aps_sintetico tudo --cenario demo --distritos 1,2,3,4,5,6,7,8 --saida saida/dev --sem-banco --sem-mlflow`
   (ou use a saída do cenário `base`).
2. Mapa real: baixe a malha de BAIRROS do Recife (dados abertos da Prefeitura) e rode
   `python painel/gerar_geojson_ds.py bairros_recife.geojson`. Isso cria `painel/assets/distritos_sanitarios.geojson`
   (requer `pip install shapely`). Sem esse arquivo, o painel mostra barras por DS.
3. Rode: `streamlit run painel/app.py -- --saida saida/dev`
