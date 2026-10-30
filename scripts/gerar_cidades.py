"""Gera a área de voo de cada município de SC para o jogo (cidades/<cod>.js + dados/municipios.js).

Uso: gerar_cidades.py PASTA_DADOS PASTA_REPO [cod ...]

PASTA_DADOS precisa de:
  edif_sc_mun.parquet   edificações Overture (centroide, área, município, urbano) — ver cruzar.py
  censo2022_sc.json     população e domicílios (Censo 2022) — ver ibge_sc.py
  malha_sc.geojson      limites municipais IBGE
  ruas_sc.parquet, agua_sc.parquet, bairros_sc.parquet, marcos_sc.json — ver overture_mapa_sc.py

Área de voo: quadrado em torno do pico de densidade urbana (a sede), com lado proporcional
ao espalhamento das edificações urbanas. Entram todas as edificações dentro do quadrado.
Cada edificação vai em 5 bytes: x e y (uint16, relativos ao quadrado) e lado (uint8, decímetros/2).

Para o jogador reconhecer a cidade, vão junto (coordenadas uint16 no mesmo quadrado):
  linhas  eixos de via e rios: [nível u8][nº de pontos u16][x y]...  nível 0 = rua, 1 = avenida, 2 = rodovia, 3 = rio
  agua    mar, lagos e rios largos: [nº de anéis u16] e, por anel, [nº de pontos u16][x y]...
  rot     nomes de bairros, localidades e rios: [nome, x, y, tipo]  tipo 0 = bairro, 1 = localidade, 2 = rio
  areas   limite de cada bairro, onde o OSM tem: [nome, polígonos no formato de "agua"]
  marcos  prefeitura e igreja matriz: [tipo, x, y]; o drone decola da prefeitura ("ini")
"""
import base64, json, struct, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.ndimage import gaussian_filter
import shapely
from shapely import STRtree
from shapely.geometry import shape, box
from shapely.ops import transform as shp_transform

D, REPO = Path(sys.argv[1]), Path(sys.argv[2])
SO = set(sys.argv[3:])
OUT = REPO / "cidades"
OUT.mkdir(parents=True, exist_ok=True)

R_MIN, R_MAX = 700.0, 5200.0   # meio-lado da área de voo (m)
LIMITE = 140_000               # teto de edificações por cidade (as menores saem primeiro)

tr = Transformer.from_crs(4326, 31982, always_xy=True)  # SIRGAS 2000 / UTM 22S
pts = pd.read_parquet(D / "edif_sc_mun.parquet")
pts = pts[pts["area_m2"] >= 8].copy()
pts["x"], pts["y"] = tr.transform(pts["cx"].to_numpy(), pts["cy"].to_numpy())
grupos = {str(k): g for k, g in pts.groupby("mun")}
malha = json.loads((D / "malha_sc.geojson").read_text(encoding="utf-8"))
polis = {f["properties"]["codarea"]: shp_transform(tr.transform, shape(f["geometry"])) for f in malha["features"]}
censo = {c["cod"]: c for c in json.loads((D / "censo2022_sc.json").read_text(encoding="utf-8"))}


def utm(df):
    """Geometrias WKB (graus) → UTM 22S, num índice espacial."""
    g = shapely.from_wkb(df["wkb"].to_numpy())
    g = shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))
    return g, STRtree(g)


NIVEL = {"residential": 0, "unclassified": 0, "living_street": 0, "tertiary": 1, "secondary": 1,
         "primary": 2, "trunk": 2, "motorway": 2}
ruas = pd.read_parquet(D / "ruas_sc.parquet")
ruas_g, ruas_t = utm(ruas)
ruas_nv = ruas["class"].map(NIVEL).to_numpy()
agua = pd.read_parquet(D / "agua_sc.parquet")
agua_g, agua_t = utm(agua)
areas = pd.read_parquet(D / "bairros_area_sc.parquet")
areas_g, areas_t = utm(areas)
bairros = pd.read_parquet(D / "bairros_sc.parquet")
bairros["x"], bairros["y"] = tr.transform(bairros["lon"].to_numpy(), bairros["lat"].to_numpy())
marcos = pd.DataFrame(json.loads((D / "marcos_sc.json").read_text(encoding="utf-8")))
marcos["x"], marcos["y"] = tr.transform(marcos["lon"].to_numpy(), marcos["lat"].to_numpy())
LIXO = ("loteamento", "residencial", "condominio", "conjunto habitacional", "chacara")


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def q16(a, x0, y0, lado):
    """Pontos UTM (n×2) → bytes [x y] uint16 no quadrado (y para baixo, como na tela)."""
    p = np.empty(len(a) * 2, dtype="<u2")
    p[0::2] = np.clip(np.round((a[:, 0] - x0) / lado * 65535), 0, 65535)
    p[1::2] = np.clip(np.round((1 - (a[:, 1] - y0) / lado) * 65535), 0, 65535)
    return p.tobytes()


def partes(g, tipo):
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == tipo and not p.is_empty]


def no_quadrado(df, x0, y0, lado, perto):
    df = df[(df["x"] >= x0) & (df["x"] < x0 + lado) & (df["y"] >= y0) & (df["y"] < y0 + lado)]
    return df[shapely.contains_xy(perto, df["x"].to_numpy(), df["y"].to_numpy())]


def poligonos(g, x0, y0, lado, tol, area_min=0):
    """Polígonos já recortados → bytes [nº de anéis u16] e, por anel, [nº de pontos u16][x y]..."""
    out = bytearray()
    for p in partes(g, "Polygon"):
        if p.area < area_min:
            continue
        p = p.simplify(tol)
        aneis = [np.asarray(r.coords) for r in [p.exterior, *p.interiors] if 4 <= len(r.coords) < 65536]
        if aneis:
            out += struct.pack("<H", len(aneis))
            for a in aneis:
                out += struct.pack("<H", len(a)) + q16(a, x0, y0, lado)
    return out


def camadas(cod, poly, x0, y0, lado, cx, cy):
    """Ruas, rios, água, nomes e marcos do quadrado de voo."""
    q, x1, y1 = box(x0, y0, x0 + lado, y0 + lado), x0 + lado, y0 + lado
    tol = lado / 4000
    lin = bytearray()
    for i in ruas_t.query(q):
        for p in partes(shapely.clip_by_rect(ruas_g[i], x0, y0, x1, y1), "LineString"):
            a = np.asarray(p.simplify(tol).coords)
            if len(a) >= 2:
                lin += struct.pack("<BH", ruas_nv[i], len(a)) + q16(a, x0, y0, lado)
    pol, rios = bytearray(), {}
    for i in agua_t.query(q):
        g = shapely.clip_by_rect(agua_g[i], x0, y0, x1, y1)
        sub, nome = agua["subtype"].iat[i], agua["nome"].iat[i]
        for p in partes(g, "LineString"):
            if sub not in ("river", "canal"):
                continue
            a = np.asarray(p.simplify(tol).coords)
            if len(a) >= 2:
                lin += struct.pack("<BH", 3, len(a)) + q16(a, x0, y0, lado)
            if nome and sub == "river":
                rios.setdefault(nome, []).append(p)
        pol += poligonos(g, x0, y0, lado, tol, 800)

    def xy(x, y):
        return round((x - x0) / lado, 4), round(1 - (y - y0) / lado, 4)

    # nomes: só o que fica dentro do município (as edificações também são só dele)
    perto = poly.buffer(50)
    b = no_quadrado(bairros, x0, y0, lado, perto)
    nome_mun = sem_acento(censo[cod]["nome"])
    b = b[~b["nome"].map(lambda t: sem_acento(t).startswith(LIXO) or sem_acento(t) == nome_mun).astype(bool)]   # astype: vazio vira objeto
    # bairro oficial = macrohood; se a cidade tem poucos, entram também os bairros menores
    tipos = ["macrohood"] if (b["subtype"] == "macrohood").sum() >= 3 else ["macrohood", "neighborhood"]
    rot, vistos = [], set()
    for sub, tp in [*[(t, 0) for t in tipos], ("locality", 1)]:
        for r in b[b["subtype"] == sub].itertuples():
            if sem_acento(r.nome) not in vistos:
                vistos.add(sem_acento(r.nome))
                rot.append([r.nome, *xy(r.x, r.y), tp])
    # limites de bairro (o HUD diz em que bairro o drone está só onde o limite existe)
    ia = [i for i in areas_t.query(q) if perto.contains(areas_g[i].representative_point())]
    sub_a = areas["subtype"].to_numpy()
    tipos_a = ["macrohood"] if sum(sub_a[i] == "macrohood" for i in ia) >= 3 else ["macrohood", "neighborhood"]
    lim = []
    for i in sorted(ia, key=lambda i: tipos_a.index(sub_a[i]) if sub_a[i] in tipos_a else 9):
        if sub_a[i] in tipos_a and not sem_acento(areas["nome"].iat[i]).startswith(LIXO):
            bb = poligonos(shapely.clip_by_rect(areas_g[i], x0, y0, x1, y1), x0, y0, lado, tol)
            if bb:
                lim.append([areas["nome"].iat[i], base64.b64encode(bytes(bb)).decode("ascii")])
    for nome, ps in sorted(rios.items(), key=lambda kv: -sum(p.length for p in kv[1]))[:3]:
        if sum(p.length for p in ps) > lado * 0.25:
            m = max(ps, key=lambda p: p.length).interpolate(0.5, normalized=True)
            rot.append([nome, *xy(m.x, m.y), 2])
    # marcos: o OSM (mapeado à mão) antes do Overture. Do Overture (Meta/Microsoft), só com 2 registros
    # concordando a menos de 200 m, para não pôr a prefeitura no lugar errado
    mk, ini = [], None
    mq = no_quadrado(marcos, x0, y0, lado, perto)
    for tipo in ("prefeitura", "matriz"):
        c = mq[mq["tipo"] == tipo]
        n = c["nome"].fillna("").map(sem_acento)
        osm, ov = c["fonte"] == "osm", (c["fonte"] == "overture") & (c["conf"] >= 0.5)
        if tipo == "prefeitura":
            th = c["townhall"] if "townhall" in c else pd.Series("", index=c.index)
            osm &= n.str.contains("prefeitura|paco municipal|centro administrativo") | ((th == "city") & ~n.str.contains("camara"))
            ov &= n.str.contains(nome_mun.split()[-1], regex=False) | n.isin(["prefeitura", "prefeitura municipal"])
        r = None
        if osm.any():
            cand = c[osm]
            r = cand.loc[np.hypot(cand["x"] - cx, cand["y"] - cy).idxmin()]
        elif ov.sum() >= 2:
            cand = c[ov]
            p = cand[["x", "y"]].to_numpy()
            viz = (np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1]) < 200).sum(1)
            fortes = cand.assign(viz=viz)[(viz >= 2) & (cand["conf"] >= 0.8)]
            if len(fortes):
                r = fortes.sort_values(["viz", "conf"]).iloc[-1]
        if r is not None and np.hypot(r["x"] - cx, r["y"] - cy) < lado * 0.45:
            mk.append([tipo, *xy(r["x"], r["y"])])
            if tipo == "prefeitura":
                ini = list(xy(r["x"], r["y"]))
    return {"linhas": base64.b64encode(bytes(lin)).decode("ascii"), "agua": base64.b64encode(bytes(pol)).decode("ascii"),
            "rot": rot, "areas": lim, "marcos": mk, "ini": ini}


def centro_urbano(u):
    """Pico de área construída urbana (grade de 100 m suavizada; cidade grande suaviza mais,
    para achar o centro e não o bairro mais denso)."""
    x0, y0 = u["x"].min() - 3000, u["y"].min() - 3000
    ix = ((u["x"] - x0) // 100).astype(int).to_numpy()
    iy = ((u["y"] - y0) // 100).astype(int).to_numpy()
    h = np.zeros((iy.max() + 31, ix.max() + 31), dtype=np.float32)
    np.add.at(h, (iy, ix), np.clip(u["area_m2"].to_numpy(), 20, 2000))
    h = gaussian_filter(h, float(np.clip(np.sqrt(len(u)) / 15, 3, 12)), mode="constant")
    j, i = np.unravel_index(np.argmax(h), h.shape)
    return x0 + (i + 0.5) * 100, y0 + (j + 0.5) * 100


def contorno(poly, x0, y0, lado):
    """Limite municipal recortado à área de voo, em coordenadas 0..1 (simplificado)."""
    q = poly.intersection(box(x0, y0, x0 + lado, y0 + lado)).simplify(lado / 1500)
    gs = getattr(q, "geoms", [q])
    aneis = []
    for g in gs:
        if g.geom_type != "Polygon" or g.is_empty:
            continue
        for anel in [g.exterior, *g.interiors]:
            a = np.asarray(anel.coords)
            aneis.append([[round((x - x0) / lado, 4), round(1 - (y - y0) / lado, 4)] for x, y in a])
    return aneis


lista = []
cods = sorted(censo) if not SO else sorted(SO)
for n, cod in enumerate(cods, 1):
    g = grupos[cod]
    u = g[g["urb"]]
    if len(u) < 50:
        u = g
    cx, cy = centro_urbano(u)
    d = np.hypot(u["x"] - cx, u["y"] - cy)
    r = float(np.clip(np.quantile(d, 0.8) * 1.15, R_MIN, R_MAX))
    lado = 2 * r
    x0, y0 = cx - r, cy - r
    dentro = g[(g["x"] >= x0) & (g["x"] < x0 + lado) & (g["y"] >= y0) & (g["y"] < y0 + lado)]
    if len(dentro) > LIMITE:
        dentro = dentro.nlargest(LIMITE, "area_m2")
    dentro = dentro.sample(frac=1, random_state=7)  # ordem aleatória: o desenho progressivo fica uniforme
    qx = np.clip((dentro["x"].to_numpy() - x0) / lado * 65535, 0, 65535).astype("<u2")
    qy = np.clip((1 - (dentro["y"].to_numpy() - y0) / lado) * 65535, 0, 65535).astype("<u2")
    s = np.clip(np.sqrt(dentro["area_m2"].to_numpy()) * 5, 1, 255).astype("u1")  # lado em 0,2 m
    buf = np.empty(len(dentro) * 5, dtype="u1")
    buf[0::5], buf[1::5] = qx.view("u1")[0::2], qx.view("u1")[1::2]
    buf[2::5], buf[3::5] = qy.view("u1")[0::2], qy.view("u1")[1::2]
    buf[4::5] = s
    c = censo[cod]
    cidade = {
        "c": cod, "n": c["nome"], "x0": round(x0, 1), "y0": round(y0, 1), "lado": round(lado, 1),
        "total": int(len(dentro)), "edifMun": int(len(g)), "edifUrb": int(g["urb"].sum()),
        "limite": contorno(polis[cod], x0, y0, lado),
        **camadas(cod, polis[cod], x0, y0, lado, cx, cy),
        "b": base64.b64encode(buf.tobytes()).decode("ascii"),
    }
    (OUT / f"{cod}.js").write_text("window.carregarCidade(" + json.dumps(cidade, ensure_ascii=False, separators=(",", ":")) + ");\n", encoding="utf-8")
    lista.append({"c": cod, "n": c["nome"], "pop": int(c["pop"]), "edif": int(len(g)), "edifUrb": int(g["urb"].sum()), "voo": int(len(dentro))})
    if n % 25 == 0 or SO:
        print(n, c["nome"], f"r={r:.0f} m", len(dentro), "edif", flush=True)

if not SO:
    lista.sort(key=lambda x: x["n"])
    js = ("// Gerado por scripts/gerar_cidades.py. Fontes: Overture Maps Foundation, release 2026-10-21.0 (edificações);\n"
          "// IBGE, Censo 2022 e setores censitários 2022 (área urbana).\n"
          "window.MUNICIPIOS = " + json.dumps(lista, ensure_ascii=False, separators=(",", ":")) + ";\n")
    (REPO / "dados" / "municipios.js").write_text(js, encoding="utf-8")
print("pronto", len(cods))
