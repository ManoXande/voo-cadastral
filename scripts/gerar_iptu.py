"""Gera dados/iptu.js: IPTU arrecadado (Siconfi), comparação com municípios do mesmo porte e a faixa de
ganho de casos reais de recadastramento.

Uso: gerar_iptu.py PASTA_REPO

Entradas (em PASTA_REPO/dados):
  iptu_sc_siconfi.csv          scripts/siconfi_iptu.py (Tesouro Nacional, DCA Anexo I-C, conta 1.1.1.2.50.0.0)
  municipios.js                scripts/gerar_cidades.py (população e edificações)
  casos_recadastramento.json   pesquisa de casos com fonte (opcional)

Faixa de ganho: só casos de confiança alta que medem arrecadação ou valor lançado de IPTU e que não
misturam aumento de alíquota. Mínimo e mediana desses casos (a mediana, e não o máximo, para não prometer demais).
"""
import json, statistics, sys
from pathlib import Path
import pandas as pd

R = Path(sys.argv[1])
D = R / "dados"
iptu = pd.read_csv(D / "iptu_sc_siconfi.csv", dtype={"cod": str})
t = (D / "municipios.js").read_text(encoding="utf-8")
mun = pd.DataFrame(json.loads(t[t.index("["):t.rindex("]") + 1])).rename(columns={"c": "cod"})
df = mun.merge(iptu[["cod", "ano", "iptu_bruto", "iptu_liquido", "iptu_bruto_2024"]], on="cod", how="left")

PORTES = [(0, 5000, "até 5 mil hab."), (5000, 10000, "5 a 10 mil hab."), (10000, 20000, "10 a 20 mil hab."),
          (20000, 50000, "20 a 50 mil hab."), (50000, 100000, "50 a 100 mil hab."), (100000, 10**9, "mais de 100 mil hab.")]
df["porte"] = df["pop"].map(lambda p: next(n for a, b, n in PORTES if a <= p < b))
df["pc"] = df["iptu_liquido"] / df["pop"]
df["pe"] = df["iptu_liquido"] / df["edifUrb"].clip(lower=1)
grupo = df.dropna(subset=["pc"]).groupby("porte").agg(pcMed=("pc", "median"), peMed=("pe", "median"), nPorte=("cod", "size"))
df = df.join(grupo, on="porte")

saida = {}
for r in df.itertuples():
    if pd.isna(r.iptu_liquido):
        continue
    saida[r.cod] = {
        "v": round(r.iptu_liquido), "b": round(r.iptu_bruto), "a": int(r.ano),
        "v24": None if pd.isna(r.iptu_bruto_2024) else round(r.iptu_bruto_2024),
        "pc": round(r.pc, 2), "pcMed": round(r.pcMed, 2), "pe": round(r.pe, 2), "peMed": round(r.peMed, 2),
        "porte": r.porte, "nPorte": int(r.nPorte),
    }

casos = None
arq = D / "casos_recadastramento.json"
if arq.exists():
    j = json.loads(arq.read_text(encoding="utf-8"))
    validos = [c for c in j.get("casos", [])
               if c.get("confianca") == "alta" and c.get("aumento_pct")
               and any(k in (c.get("o_que_mede") or "") for k in ("arrecadação", "valor lançado"))
               and "alíquota" not in (c.get("como_fizeram") or "").lower().replace("sem aumento de alíquota", "").replace("sem aumentar alíquota", "").replace("sem alterar alíquota", "")]
    if validos:
        pcts = sorted(float(c["aumento_pct"]) for c in validos)
        casos = {
            "min": round(pcts[0]), "max": round(statistics.median(pcts)), "n": len(pcts),
            "fonteCurta": ", ".join(f"{c['municipio']}/{c['uf']}" for c in validos[:4]) + (" e outros" if len(validos) > 4 else ""),
            "casos": [{k: c.get(k) for k in ("municipio", "uf", "ano", "o_que_mede", "antes", "depois", "aumento_pct", "como_fizeram", "fonte_titulo", "fonte_url")} for c in validos],
        }

js = ("// Gerado por scripts/gerar_iptu.py. IPTU: Tesouro Nacional, Siconfi, DCA Anexo I-C (receita líquida da conta 1.1.1.2.50.0.0).\n"
      "// v = IPTU líquido do ano a; pc/pcMed = por habitante (município / mediana do porte em SC); pe/peMed = por edificação urbana.\n"
      "window.IPTU = " + json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + ";\n"
      "window.CASOS_RECADASTRO = " + json.dumps(casos, ensure_ascii=False, separators=(",", ":")) + ";\n")
(D / "iptu.js").write_text(js, encoding="utf-8")
print(len(saida), "municípios com IPTU;", "casos:", casos and (casos["n"], casos["min"], casos["max"]))
print(grupo.round(2).to_string())
for cod in ("4204202", "4215695", "4207700", "4205407"):
    print(cod, saida.get(cod))
