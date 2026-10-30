"""Censo 2022 por município de SC + malha municipal (IBGE). Uso: ibge_sc.py PASTA_SAIDA"""
import gzip, json, sys, urllib.request
from pathlib import Path

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
API = "https://servicodados.ibge.gov.br/api/v3/agregados"

def get(url):
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

def meta(t):
    return get(f"{API}/{t}/metadados")

def consulta(tabela, var, classif=""):
    url = f"{API}/{tabela}/periodos/2022/variaveis/{var}?localidades=N6[N3[42]]"
    if classif:
        url += f"&classificacao={classif}"
    out = {}
    for v in get(url):
        for r in v["resultados"]:
            rot = "|".join(list(c["categoria"].values())[0] for c in r["classificacoes"])
            for s in r["series"]:
                val = s["serie"].get("2022")
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    val = None
                out.setdefault(s["localidade"]["id"], {})[rot] = val
    return out

mun = {str(m["id"]): m["nome"] for m in get("https://servicodados.ibge.gov.br/api/v1/localidades/estados/42/municipios")}
pop = consulta(4709, 93)
dom = consulta(4711, 617, "3[59993,59998,60001]")
m9923 = meta(9923)
c9923 = m9923["classificacoes"][0]
sit = consulta(9923, 93, f"{c9923['id']}[{','.join(str(c['id']) for c in c9923['categorias'])}]")
idade = consulta(9514, 93, "287[6557,6558,6559,6560,6561,6562]")

linhas = []
for cod, nome in sorted(mun.items(), key=lambda x: x[1]):
    d = dom.get(cod, {}); s = sit.get(cod, {}); i = idade.get(cod, {})
    def pega(dic, chave):
        for k, v in dic.items():
            if chave in k:
                return v
        return None
    idades = {k.split("|")[-1] if "|" in k else k: v for k, v in i.items()}
    def soma(nomes):
        vals = [v for k, v in i.items() if any(k.endswith(n) or k.startswith(n) or f"|{n}" in k for n in nomes)]
        return sum(x for x in vals if x is not None) if vals else None
    linhas.append({
        "cod": cod, "nome": nome,
        "pop": list(pop.get(cod, {None: None}).values())[0],
        "dom_total": pega(d, "Total"),
        "dom_ocupados": pega(d, "Particular permanente ocupado"),
        "dom_nao_ocupados": pega(d, "Particular permanente não ocupado"),
        "pop_urbana": pega(s, "Urbana"),
        "pop_rural": pega(s, "Rural"),
        "criancas_0a3": soma(["Menos de 1 ano", "1 ano", "2 anos", "3 anos"]),
        "criancas_4a5": soma(["4 anos", "5 anos"]),
        "_idade_rotulos": sorted(i.keys()) if cod == "4204202" else None,
        "_dom_rotulos": sorted(d.keys()) if cod == "4204202" else None,
        "_sit_rotulos": sorted(s.keys()) if cod == "4204202" else None,
    })
(OUT / "censo2022_sc.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding="utf-8")
malha = get("https://servicodados.ibge.gov.br/api/v3/malhas/estados/42?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=maxima")
(OUT / "malha_sc.geojson").write_text(json.dumps(malha), encoding="utf-8")
print(len(linhas), "municipios;", len(malha["features"]), "poligonos")
print(json.dumps([l for l in linhas if l["cod"] == "4204202"], ensure_ascii=False, indent=1))
