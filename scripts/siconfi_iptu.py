"""IPTU arrecadado pelos municipios de SC, a partir da DCA (Siconfi / Tesouro Nacional).

Fonte: API de dados abertos do Siconfi
  https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca
  ?an_exercicio=<ano>&no_anexo=DCA-Anexo I-C&id_ente=<cod IBGE 7 digitos>

Linha usada: cod_conta "RO1.1.1.2.50.0.0" - Imposto sobre a Propriedade Predial e
Territorial Urbana (agregado: principal + multas/juros + divida ativa).
  iptu_bruto    = coluna "Receitas Brutas Realizadas"
  iptu_deducoes = soma das colunas de deducao ("Deduções - FUNDEB",
                  "Outras Deduções da Receita", e qualquer outra "Dedu...")
  iptu_liquido  = iptu_bruto - iptu_deducoes

Ano preferido: 2025; se a DCA 2025 nao trouxer a linha do IPTU, usa 2024.

Uso:
  python siconfi_iptu.py [--entrada censo2022_sc.json] [--saida iptu_sc_siconfi.csv]

Respostas cruas ficam em cache (%TEMP%\\siconfi_cache) e nao sao baixadas de novo.
Para forcar novo download de um municipio/ano, apague o arquivo correspondente.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
ANEXO = "DCA-Anexo I-C"
CONTA_IPTU = "RO1.1.1.2.50.0.0"
PREFIXO_IPTU = "RO1.1.1.2.50"
COL_BRUTA = "Receitas Brutas Realizadas"
ANOS = (2025, 2024)  # ordem de preferencia

TEMP = Path(os.environ.get("TEMP", r"C:\Users\autha\AppData\Local\Temp"))
ENTRADA_PADRAO = TEMP / "comac_ativ" / "dados" / "censo2022_sc.json"
SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "iptu_sc_siconfi.csv"
CACHE_PADRAO = TEMP / "siconfi_cache"

INTERVALO = 1.0  # segundos entre requisicoes reais
_ultima_req = 0.0


def _get(url: str, tentativas: int = 7) -> dict:
    """GET com ~1 req/s e retry com espera em 429/5xx/erro de rede."""
    global _ultima_req
    espera = 5.0
    for t in range(1, tentativas + 1):
        dt = time.monotonic() - _ultima_req
        if dt < INTERVALO:
            time.sleep(INTERVALO - dt)
        _ultima_req = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "siconfi_iptu.py"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                ra = e.headers.get("Retry-After") if e.headers else None
                pausa = float(ra) if ra and ra.isdigit() else espera
                print(f"  HTTP {e.code}; tentativa {t}/{tentativas}, aguardando {pausa:.0f}s",
                      file=sys.stderr)
                time.sleep(pausa)
                espera = min(espera * 2, 120)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            print(f"  erro de rede ({e}); tentativa {t}/{tentativas}, aguardando {espera:.0f}s",
                  file=sys.stderr)
            time.sleep(espera)
            espera = min(espera * 2, 120)
    raise RuntimeError(f"falhou apos {tentativas} tentativas: {url}")


def baixar_dca(cod: str, ano: int, cache: Path) -> list[dict]:
    """Todos os itens do Anexo I-C da DCA (pagina ate hasMore=False), com cache."""
    itens: list[dict] = []
    offset = 0
    while True:
        arq = cache / f"dca_I-C_{ano}_{cod}_off{offset}.json"
        if arq.exists():
            dados = json.loads(arq.read_text(encoding="utf-8"))
        else:
            q = urllib.parse.urlencode({"an_exercicio": ano, "no_anexo": ANEXO,
                                        "id_ente": cod, "offset": offset},
                                       quote_via=urllib.parse.quote)
            dados = _get(f"{API}?{q}")
            if "items" not in dados:
                raise RuntimeError(f"resposta inesperada para {cod}/{ano}: {str(dados)[:200]}")
            arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        lote = dados.get("items", [])
        itens.extend(lote)
        if not dados.get("hasMore") or not lote:
            return itens
        offset += len(lote)


def extrair_iptu(itens: list[dict]) -> dict | None:
    """Bruto/deducoes do IPTU. Prefere a linha agregada; se faltar, soma as
    sublinhas de menor nivel abaixo de 1.1.1.2.50 (e registra isso em 'conta')."""
    linhas = [i for i in itens if i.get("cod_conta") == CONTA_IPTU]
    conta = CONTA_IPTU[2:]
    if not linhas:
        sub = [i for i in itens if str(i.get("cod_conta", "")).startswith(PREFIXO_IPTU)]
        if not sub:
            return None
        # menor nivel = conta com mais zeros finais (mais agregada)
        def nivel(c: str) -> int:
            return len(c.rstrip("0.")) if c else 99
        menor = min(nivel(i["cod_conta"]) for i in sub)
        linhas = [i for i in sub if nivel(i["cod_conta"]) == menor]
        conta = "+".join(sorted({i["cod_conta"][2:] for i in linhas}))
    bruto = 0.0
    ded = 0.0
    tem_bruto = False
    vistos: set[tuple] = set()
    duplicadas = False
    for i in linhas:
        chave = (i.get("cod_conta"), i.get("coluna"), i.get("instituicao"), i.get("rotulo"))
        if chave in vistos:
            duplicadas = True
        vistos.add(chave)
        col = i.get("coluna", "")
        v = float(i.get("valor") or 0.0)
        if col == COL_BRUTA:
            bruto += v
            tem_bruto = True
        elif col.startswith("Dedu") or col.startswith("Outras Dedu"):
            ded += v
    if not tem_bruto:
        return None
    return {"bruto": round(bruto, 2), "deducoes": round(ded, 2),
            "liquido": round(bruto - ded, 2), "conta": conta,
            "duplicadas": duplicadas,
            "colunas": sorted({i.get("coluna", "") for i in linhas})}


def fmt(v) -> str:
    return "" if v is None else f"{v:.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--cache", type=Path, default=CACHE_PADRAO)
    a = ap.parse_args()

    munis = json.loads(a.entrada.read_text(encoding="utf-8"))
    a.cache.mkdir(parents=True, exist_ok=True)
    a.saida.parent.mkdir(parents=True, exist_ok=True)

    linhas_csv = []
    avisos = []
    colunas_vistas: set[str] = set()
    cont = {2025: 0, 2024: 0, None: 0}

    for n, m in enumerate(munis, 1):
        cod, nome = str(m["cod"]).strip(), m["nome"]
        res: dict[int, dict | None] = {}
        nitens: dict[int, int] = {}
        for ano in ANOS:
            itens = baixar_dca(cod, ano, a.cache)
            nitens[ano] = len(itens)
            res[ano] = extrair_iptu(itens)
            if res[ano]:
                colunas_vistas.update(res[ano]["colunas"])
                if res[ano]["duplicadas"]:
                    avisos.append(f"{cod} {nome} {ano}: linhas de IPTU duplicadas na resposta")
                if res[ano]["conta"] != CONTA_IPTU[2:]:
                    avisos.append(f"{cod} {nome} {ano}: sem a linha agregada; usou {res[ano]['conta']}")
            elif nitens[ano]:
                avisos.append(f"{cod} {nome} {ano}: DCA entregue ({nitens[ano]} itens) mas sem linha de IPTU")

        ano_usado = next((ano for ano in ANOS if res[ano]), None)
        cont[ano_usado] += 1
        r = res[ano_usado] if ano_usado else None
        b24 = res[2024]["bruto"] if res[2024] else None
        b25 = res[2025]["bruto"] if res[2025] else None
        if b24 and b25 and not (0.5 <= b25 / b24 <= 2.0):
            avisos.append(f"{cod} {nome}: variacao 2024->2025 fora de 0,5x-2x "
                          f"({b24:,.2f} -> {b25:,.2f})")
        linhas_csv.append({
            "cod": cod, "nome": nome,
            "ano": ano_usado if ano_usado else "",
            "iptu_bruto": fmt(r["bruto"]) if r else "",
            "iptu_deducoes": fmt(r["deducoes"]) if r else "",
            "iptu_liquido": fmt(r["liquido"]) if r else "",
            "iptu_bruto_2024": fmt(b24), "iptu_bruto_2025": fmt(b25),
            "conta": r["conta"] if r else "",
        })
        print(f"[{n:3d}/{len(munis)}] {cod} {nome}: ano={ano_usado} "
              f"bruto={fmt(r['bruto']) if r else '-'} (itens 2025={nitens[2025]}, 2024={nitens[2024]})",
              flush=True)

    campos = ["cod", "nome", "ano", "iptu_bruto", "iptu_deducoes", "iptu_liquido",
              "iptu_bruto_2024", "iptu_bruto_2025", "conta"]
    with a.saida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas_csv)

    print(f"\nGravado: {a.saida}")
    print(f"Com 2025: {cont[2025]} | com 2024: {cont[2024]} | sem dado: {cont[None]}")
    print(f"Colunas encontradas nas linhas de IPTU: {sorted(colunas_vistas)}")
    if avisos:
        print("\nAvisos:")
        for x in avisos:
            print("  -", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
