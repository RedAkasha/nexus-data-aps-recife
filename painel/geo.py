"""Malha de bairros do Recife -> bairros com Distrito Sanitário (DS) + contorno de cada DS.

Entrada: o GeoJSON de bairros da Prefeitura (dados.recife.pe.gov.br, "Bairros do Recife",
arquivo bairros-do-recife.geojson) salvo em painel/assets/. O arquivo pode estar em graus
(WGS84) ou em metros (UTM/SIRGAS 2000); o carregador percebe e converte. Cada bairro recebe o DS de
dados/estrutura/bairro.csv. O casamento é pelo nome (sem acento e caixa), com tolerância para
"A - B" e pequenas variações de grafia; o que não casar é listado no diagnóstico, nunca escondido.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).parent / "assets"
SIMPLIFICA = 0.0001          # ~11 m: o mapa fica leve sem perder o desenho dos bairros


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    for ch in "-–.,/()":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def arquivo_malha() -> Path | None:
    """Primeiro .geojson/.json de painel/assets (prefere o nome oficial)."""
    if not ASSETS.exists():
        return None
    achados = sorted(list(ASSETS.glob("*.geojson")) + list(ASSETS.glob("*.json")))
    pref = [p for p in achados if "bairro" in p.name.lower()]
    return (pref or achados or [None])[0]


def _coords(g):
    if isinstance(g, (list, tuple)):
        if g and isinstance(g[0], (int, float)):
            yield g
        else:
            for x in g:
                yield from _coords(x)


def _transformador(gj: dict):
    """Função de reprojeção para graus, ou None se já estiver em graus."""
    amostra = next((c for f in gj["features"] for c in _coords(f["geometry"]["coordinates"])), None)
    if amostra is None or (abs(amostra[0]) <= 180 and abs(amostra[1]) <= 90):
        return None
    from pyproj import Transformer          # só é necessário para malhas em metros
    nome = str(((gj.get("crs") or {}).get("properties") or {}).get("name", ""))
    achou = re.findall(r"(?:EPSG[:/]+)(\d{4,5})", nome)
    epsg = f"EPSG:{achou[-1]}" if achou and achou[-1] != "4326" else "EPSG:31985"   # padrão: SIRGAS 2000 / UTM 25S
    t = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
    return lambda x, y, z=None: t.transform(x, y)


def _acha_ds(nome: str, ref: dict, ref_nomes: list[str]):
    """(id_bairro, id_ds, como) pelo nome do bairro da malha."""
    n = norm(nome)
    if n in ref:
        return (*ref[n], "exato")
    for parte in [norm(p) for p in str(nome).split(" - ")]:
        if parte in ref:
            return (*ref[parte], "parte do nome")
    for k in ref:                           # "sitio dos pintos" dentro de "sitio dos pintos sao bras"
        if len(n) >= 6 and (n in k or k in n):
            return (*ref[k], "contido no nome")
    p = difflib.get_close_matches(n, ref_nomes, n=1, cutoff=0.88)
    return (*ref[p[0]], f"aproximado ({p[0]})") if p else (None, None, "sem correspondência")


def carregar(caminho: str | Path) -> dict:
    """Devolve {'bairros': [...], 'ds': [...], 'rotulos': [...], 'diag': DataFrame}."""
    gj = json.loads(Path(caminho).read_text(encoding="utf-8"))
    feats = gj["features"]
    ref_df = pd.read_csv(RAIZ / "dados" / "estrutura" / "bairro.csv")
    ref = {norm(n): (int(i), int(d)) for i, n, d in zip(ref_df["id_bairro"], ref_df["nome_bairro"], ref_df["id_ds"])}
    ref_nomes = list(ref)
    # propriedade que guarda o nome do bairro = a que mais casa com a referência
    chaves = {k for f in feats for k in (f.get("properties") or {})}
    chave = max(chaves, key=lambda k: sum(norm((f.get("properties") or {}).get(k)) in ref for f in feats))
    reproj = _transformador(gj)
    bairros, linhas, por_ds = [], [], {}
    for f in feats:
        nome = (f.get("properties") or {}).get(chave, "")
        g = shape(f["geometry"])
        if reproj is not None:
            g = transform(reproj, g)
        g = g.buffer(0)
        id_b, id_ds, como = _acha_ds(nome, ref, ref_nomes)
        linhas.append({"bairro_na_malha": nome, "id_bairro": id_b, "id_ds": id_ds, "casamento": como})
        gs = g.simplify(SIMPLIFICA, preserve_topology=True)
        bairros.append({"type": "Feature", "geometry": mapping(gs), "properties": {
            "bairro": str(nome).title() if str(nome).isupper() else str(nome), "id_bairro": id_b,
            "id_ds": id_ds, "DS": f"DS {id_ds}" if id_ds else "Sem DS"}})
        if id_ds:
            por_ds.setdefault(id_ds, []).append(g)
    ds_feats, rotulos = [], []
    for d, gs in sorted(por_ds.items()):
        u = unary_union(gs).simplify(SIMPLIFICA, preserve_topology=True)
        ds_feats.append({"type": "Feature", "geometry": mapping(u), "properties": {"id_ds": d, "DS": f"DS {d}"}})
        p = u.representative_point()
        rotulos.append({"id_ds": d, "DS": f"DS {d}", "lon": p.x, "lat": p.y})
    return {"bairros": bairros, "ds": ds_feats, "rotulos": rotulos, "diag": pd.DataFrame(linhas),
            "propriedade_nome": chave, "reprojetado": reproj is not None}
