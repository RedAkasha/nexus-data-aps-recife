# Painel Nexus Data – como usar

Estes arquivos substituem os de mesmo nome no repositório (`painel/`, `.streamlit/`, `pyproject.toml`, `requirements.txt`).

1. Instale: `pip install -e ".[painel]"` (traz streamlit, altair, shapely e pyproj).
2. Gere os dados sintéticos (8 DS): `python -m aps_sintetico tudo --cenario demo --distritos 1,2,3,4,5,6,7,8 --saida saida/dev --sem-banco --sem-mlflow`
   (ou use a saída do cenário `base`).
3. **Mapa:** já vem incluído em `painel/assets/bairros-do-recife.geojson`. Se precisar trocar, baixe `bairros-do-recife.geojson` no portal de dados abertos da Prefeitura
   (https://dados.recife.pe.gov.br/dataset/area-urbana, recurso "Bairros do Recife", formato GeoJSON) e salve em
   `painel/assets/`. Não precisa converter nada: o painel liga cada bairro ao seu Distrito Sanitário pelo nome
   (`dados/estrutura/bairro.csv`), converte de metros para graus se for preciso e junta os bairros de cada DS.
   Se algum bairro não casar, ele aparece no expander "Diagnóstico da malha" na Visão Geral.
4. Rode: `streamlit run painel/app.py -- --saida saida/dev`

Sem o GeoJSON o painel funciona e mostra barras por DS no lugar do mapa.

Páginas: **Visão Geral** (cartões, mapa, tendência, ranking), **Ad. Preenchimento** (completude por campo, por DS e no
tempo, ranking por equipe, planilha SESAU) e **Prevenção IA**, que só lê `saida/<cenário>/ml/predicoes.parquet`
(colunas `ine, periodo, id_ds, prop_sim_os, previsto`; `modelo` é opcional). O modelo final pode ser trocado sem mexer no painel.
