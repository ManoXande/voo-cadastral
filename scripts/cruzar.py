"""Cruza edificações (Overture) com setores censitários 2022: município + urbano/rural."""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely

D = Path(sys.argv[1])
t = time.time()
pts = pd.read_parquet(D / "overture_sc.parquet")
set_ = gpd.read_file(D / "setores" / "SC_setores_CD2022.shp", columns=["CD_MUN", "CD_SIT", "SITUACAO"])
set_ = set_.to_crs(4326)
print("lido", len(pts), len(set_), f"{time.time()-t:.0f}s", flush=True)
geoms = shapely.points(pts["cx"].to_numpy(), pts["cy"].to_numpy())
tree = shapely.STRtree(set_.geometry.values)
ip, isg = tree.query(geoms, predicate="intersects")
# ponto na divisa de dois setores: fica o primeiro
_, first = np.unique(ip, return_index=True)
ip, isg = ip[first], isg[first]
print("cruzado", len(ip), f"{time.time()-t:.0f}s", flush=True)
mun = np.full(len(pts), -1, dtype=np.int64)
urb = np.zeros(len(pts), dtype=bool)
mun[ip] = set_["CD_MUN"].astype(np.int64).to_numpy()[isg]
urb[ip] = (set_["SITUACAO"].to_numpy()[isg] == "Urbana")
pts["mun"] = mun
pts["urb"] = urb
pts = pts[pts["mun"] >= 0].reset_index(drop=True)
pts.to_parquet(D / "edif_sc_mun.parquet")
g = pts.groupby("mun")
st = pd.DataFrame({
    "edif": g.size(),
    "edif_urb": g["urb"].sum(),
    "area_m2": g["area_m2"].sum(),
    "area_urb_m2": pts[pts["urb"]].groupby("mun")["area_m2"].sum(),
    "edif_40m2": pts[pts["area_m2"] >= 40].groupby("mun").size(),
}).fillna(0)
st.index = st.index.astype(str)
st.to_csv(D / "edif_por_municipio.csv")
print("municipios", len(st), "edif SC", int(st["edif"].sum()), "urb", int(st["edif_urb"].sum()), f"{time.time()-t:.0f}s")
print(st.loc[["4204202", "4207650", "4202008"]] if "4207650" in st.index else st.head())
