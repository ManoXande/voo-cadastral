"""Baixa o que faz o mapa parecer a cidade: ruas, água, bairros e marcos (prefeitura e igreja matriz) de SC.

Uso: overture_mapa_sc.py PASTA_DADOS

Grava em PASTA_DADOS:
  ruas_sc.parquet      eixos de via do Overture (classe, nome, WKB)
  agua_sc.parquet      mar, lagos, rios e canais do Overture (subtipo, nome, WKB)
  bairros_sc.parquet   bairros e localidades do Overture (vindos do OSM): subtipo, nome, ponto
  bairros_area_sc.parquet  limites dos bairros, onde o OSM tem (para dizer em que bairro o drone está)
  marcos_sc.json       prefeituras e igrejas matriz: OSM (Nominatim) e Overture places
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path
import duckdb

REL = "2026-10-21.0"
D = Path(sys.argv[1])
S3 = f"s3://overturemaps-us-west-2/release/{REL}"
SC = "bbox.xmin > -53.95 AND bbox.xmax < -48.25 AND bbox.ymin > -29.45 AND bbox.ymax < -25.90"
# o mar é um polígono enorme que passa da divisa: para a água vale o que toca o retângulo, não só o que cabe nele
SC_TOCA = "bbox.xmax > -53.95 AND bbox.xmin < -48.25 AND bbox.ymax > -29.45 AND bbox.ymin < -25.90"
CLASSES = "('motorway','trunk','primary','secondary','tertiary','residential','unclassified','living_street')"

con = duckdb.connect()
for ext in ("httpfs", "spatial"):
    con.execute(f"INSTALL {ext}; LOAD {ext};")
con.execute("SET s3_region='us-west-2'; SET threads=16; SET enable_progress_bar=false;")


def copiar(nome, sql):
    if (D / nome).exists():   # já baixado; apague o arquivo para baixar de novo
        return
    t = time.time()
    con.execute(f"COPY ({sql}) TO '{D / nome}' (FORMAT parquet)")
    n = con.execute(f"SELECT count(*) FROM '{D / nome}'").fetchone()[0]
    print(f"{nome}: {n} linhas, {time.time() - t:.0f} s", flush=True)


copiar("ruas_sc.parquet", f"""
  SELECT class, names.primary AS nome, ST_AsWKB(geometry) AS wkb
  FROM read_parquet('{S3}/theme=transportation/type=segment/*', hive_partitioning=1)
  WHERE {SC} AND subtype = 'road' AND class IN {CLASSES}""")
copiar("agua_sc.parquet", f"""
  SELECT subtype, class, names.primary AS nome, ST_AsWKB(geometry) AS wkb
  FROM read_parquet('{S3}/theme=base/type=water/*', hive_partitioning=1)
  WHERE {SC_TOCA} AND subtype IN ('ocean','lake','river','reservoir','water','canal','pond')
    AND class NOT IN ('swimming_pool','wastewater','drain','ditch','sewage')""")
copiar("bairros_sc.parquet", f"""
  SELECT subtype, names.primary AS nome, ST_X(geometry) AS lon, ST_Y(geometry) AS lat
  FROM read_parquet('{S3}/theme=divisions/type=division/*', hive_partitioning=1)
  WHERE {SC} AND subtype IN ('macrohood','neighborhood','locality') AND names.primary IS NOT NULL""")

copiar("bairros_area_sc.parquet", f"""
  SELECT subtype, names.primary AS nome, ST_AsWKB(geometry) AS wkb
  FROM read_parquet('{S3}/theme=divisions/type=division_area/*', hive_partitioning=1)
  WHERE {SC} AND subtype IN ('macrohood','neighborhood') AND class = 'land' AND names.primary IS NOT NULL""")

# marcos: Overture places (Meta/Microsoft) e OSM; o gerador prefere o OSM, mapeado à mão
arq_ov = D / "marcos_overture_sc.json"
if not arq_ov.exists():
    ov = con.execute(f"""
      SELECT names.primary, taxonomy.primary, confidence, ST_X(geometry), ST_Y(geometry)
      FROM read_parquet('{S3}/theme=places/type=place/*', hive_partitioning=1)
      WHERE {SC} AND (
        (taxonomy.primary = 'town_hall' AND names.primary ILIKE 'prefeitura%')
        OR (basic_category = 'christian_place_of_worship' AND names.primary ILIKE '%matriz%'))""").fetchall()
    arq_ov.write_text(json.dumps([{"fonte": "overture", "tipo": "prefeitura" if t == "town_hall" else "matriz", "nome": n, "conf": c,
                                   "lon": x, "lat": y} for n, t, c, x, y in ov], ensure_ascii=False), encoding="utf-8")
marcos = json.loads(arq_ov.read_text(encoding="utf-8"))

if (D / "marcos_sc.json").exists():   # já baixado; apague o arquivo para buscar de novo
    sys.exit()
# OSM pelo Nominatim (o Overpass vive fora do ar): 2 buscas por município, no máximo 1 por segundo (regra do Nominatim)
BUSCAS = (("prefeitura", "Prefeitura {}, Santa Catarina", lambda r: r["category"] == "amenity" and r["type"] == "townhall"),
          ("matriz", "Igreja Matriz {}, Santa Catarina",
           lambda r: r["type"] in ("place_of_worship", "church", "cathedral") and "matriz" in r["name"].lower()))
n_osm = 0
for m in json.loads((D / "censo2022_sc.json").read_text(encoding="utf-8")):
    for tipo, frase, serve in BUSCAS:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": frase.format(m["nome"]), "format": "jsonv2", "countrycodes": "br", "limit": 5})
        req = urllib.request.Request(url, headers={"User-Agent": "voo-cadastral/1.0 (Autha-Geo)"})
        try:
            res = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            print(f"Nominatim falhou em {m['nome']}: {e}", flush=True)
            res = []
        for r in res:
            if serve(r):
                marcos.append({"fonte": "osm", "tipo": tipo, "nome": r["name"], "conf": 1.0, "lon": float(r["lon"]), "lat": float(r["lat"])})
                n_osm += 1
        time.sleep(1.05)
(D / "marcos_sc.json").write_text(json.dumps(marcos, ensure_ascii=False), encoding="utf-8")
print(f"marcos_sc.json: {len(marcos) - n_osm} do Overture, {n_osm} do OSM", flush=True)
