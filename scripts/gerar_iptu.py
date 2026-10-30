"""Gera dados/iptu.js: IPTU arrecadado (Siconfi), comparação com municípios do mesmo porte e a faixa de
ganho de casos reais de recadastramento.

Uso: gerar_iptu.py PASTA_REPO

Entradas (em PASTA_REPO/dados):
  iptu_sc_siconfi.csv          scripts/siconfi_iptu.py (Tesouro Nacional, DCA Anexo I-C, conta 1.1.1.2.50.0.0)
  municipios.js                scripts/gerar_cidades.py (população e edificações)
  casos_recadastramento.json   pesquisa de casos com fonte (opcional)

Faixa de ganho: só casos de confiança alta que medem arrecadação ou valor lançado de IPTU e que, pela fonte,
não tiveram nova planta de valores nem mudança de alíquota (mistura_pgv_ou_aliquota = false). Com até 3 casos,
a faixa vai do menor ao maior; com mais, do menor à mediana. Casos que medem o cadastro (área construída achada,
imóveis corrigidos) entram à parte, como evidência de cadastro defasado.
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
ROTULO = {"Criciúma": "Criciúma/SC, que corrigiu o cadastro de um bairro (+16% no IPTU lançado)"}
CAMPOS = ("municipio", "uf", "populacao_aprox", "ano", "o_que_mede", "antes", "depois", "aumento_pct", "como_fizeram", "fonte_titulo", "fonte_url", "fonte_tipo")
if arq.exists():
    j = json.loads(arq.read_text(encoding="utf-8"))
    receita = lambda c: any(k in (c.get("o_que_mede") or "") for k in ("arrecadação", "valor lançado"))
    # "mais receita sem aumentar imposto": só casos que a fonte diz que não tiveram nova planta de valores nem alíquota
    limpos = [c for c in j.get("casos", []) if c.get("confianca") == "alta" and c.get("aumento_pct") and receita(c) and c.get("mistura_pgv_ou_aliquota") is False]
    cadastro = [c for c in j.get("casos", []) if c.get("confianca") == "alta" and not receita(c) and c.get("mistura_pgv_ou_aliquota") is not True]
    cadastro.sort(key=lambda c: (c.get("uf") != "SC", c.get("uf") not in ("PR", "RS")))
    # frase curta para a tela do jogo (mesmos números da fonte)
    FRASES = {"Chapecó": "corrigiu a área construída de 28 mil dos 142 mil imóveis — 1 em cada 5",
              "Brusque": "atualizou o cadastro de cerca de 12 mil dos 100 mil imóveis"}
    for c in cadastro:
        c["frase"] = FRASES.get(c["municipio"])
    if limpos:
        pcts = sorted(float(c["aumento_pct"]) for c in limpos)
        topo = pcts[-1] if len(pcts) <= 3 else statistics.median(pcts)   # com poucos casos, o maior; com muitos, a mediana
        casos = {
            "min": round(pcts[0]), "max": round(topo), "n": len(pcts),
            "fonteCurta": " e ".join(ROTULO.get(c["municipio"], f"{c['municipio']}/{c['uf']} (+{round(c['aumento_pct'])}%)") for c in sorted(limpos, key=lambda c: c["aumento_pct"])),
            "casos": [{k: c.get(k) for k in CAMPOS} for c in limpos],
            "cadastro": [{k: c.get(k) for k in CAMPOS + ("frase",)} for c in cadastro],
            "estudos": [{"trecho": e.get("trecho"), "fonte": f"{e.get('fonte')}, {e.get('ano')}", "titulo": e.get("titulo"), "fonte_url": e.get("fonte_url")}
                        for e in j.get("estudos_agregados", []) if e.get("fonte_url") and e.get("confianca", "alta") == "alta"],
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
