"""Gera painel/assets/distritos_sanitarios.geojson a partir da malha de BAIRROS do Recife.

Uso:
    python painel/gerar_geojson_ds.py bairros_recife.geojson

A malha de bairros está nos dados abertos da Prefeitura (dados.recife.pe.gov.br, conjunto "Bairros").
O script descobre sozinho a propriedade com o nome do bairro (a que mais casa com
dados/estrutura/bairro.csv), junta os bairros de cada Distrito Sanitário e grava um polígono por DS,
com a propriedade "ds" (1 a 8). Bairros sem correspondência são listados no final.
"""
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[1]


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def main(entrada: str):
    gj = json.loads(Path(entrada).read_text(encoding="utf-8"))
    ref = pd.read_csv(RAIZ / "dados" / "estrutura" / "bairro.csv")
    nome2ds = {norm(n): int(d) for n, d in zip(ref["nome_bairro"], ref["id_ds"])}
    feats = gj["features"]
    chaves = {k for f in feats for k in f.get("properties", {})}
    melhor = max(chaves, key=lambda k: sum(norm(f["properties"].get(k)) in nome2ds for f in feats))
    print(f"propriedade do nome do bairro: {melhor}")
    grupos, sem = {}, []
    for f in feats:
        ds = nome2ds.get(norm(f["properties"].get(melhor)))
        if ds is None:
            sem.append(f["properties"].get(melhor))
            continue
        grupos.setdefault(ds, []).append(shape(f["geometry"]).buffer(0))
    saida = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ds": ds, "nome": f"DS {ds}"},
         "geometry": mapping(unary_union(g).simplify(0.0002))} for ds, g in sorted(grupos.items())]}
    dest = Path(__file__).parent / "assets" / "distritos_sanitarios.geojson"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(saida), encoding="utf-8")
    print(f"gravado {dest} com {len(grupos)} distritos; bairros sem correspondência: {sem or 'nenhum'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
