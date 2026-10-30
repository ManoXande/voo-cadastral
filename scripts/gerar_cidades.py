"""Gera a área de voo de cada município de SC para o jogo (cidades/<cod>.js + dados/municipios.js).

Uso: gerar_cidades.py PASTA_DADOS PASTA_REPO [cod ...]

PASTA_DADOS precisa de:
  edif_sc_mun.parquet   edificações Overture (centroide, área, município, urbano) — ver cruzar.py
  censo2022_sc.json     população e domicílios (Censo 2022) — ver ibge_sc.py
  malha_sc.geojson      limites municipais IBGE

Área de voo: quadrado em torno do pico de densidade urbana (a sede), com lado proporcional
ao espalhamento das edificações urbanas. Entram todas as edificações dentro do quadrado.
Cada edificação vai em 5 bytes: x e y (uint16, relativos ao quadrado) e lado (uint8, decímetros/2).
"""
import base64, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.ndimage import gaussian_filter
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
