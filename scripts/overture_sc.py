"""Baixa as edificações do Overture Maps dentro do retângulo de SC (centroide + área)."""
import sys, time, duckdb

REL = "2026-10-21.0"
OUT = sys.argv[1]
con = duckdb.connect()
for ext in ("httpfs", "spatial"):
    con.execute(f"INSTALL {ext}; LOAD {ext};")
con.execute("SET s3_region='us-west-2'; SET threads=16; SET enable_progress_bar=false;")
t = time.time()
con.execute(f"""
COPY (
  SELECT
    (bbox.xmin + bbox.xmax) / 2 AS cx,
    (bbox.ymin + bbox.ymax) / 2 AS cy,
    ST_Area(geometry) * 111320.0 * 110574.0 * cos(radians((bbox.ymin + bbox.ymax) / 2)) AS area_m2
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/*', hive_partitioning=1)
  WHERE bbox.xmin > -53.95 AND bbox.xmax < -48.25
    AND bbox.ymin > -29.45 AND bbox.ymax < -25.90
) TO '{OUT}' (FORMAT parquet);
""")
n = con.execute(f"SELECT count(*) FROM '{OUT}'").fetchone()[0]
print(f"edificacoes={n} segundos={time.time()-t:.0f}", flush=True)
