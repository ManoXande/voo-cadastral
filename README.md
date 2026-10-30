# Voo Cadastral — Autha-Geo

Jogo de estande para a COMAC-SC 2026: o prefeito pilota um drone sobre a **própria cidade** (os 295 municípios de SC), dispara o laser cadastral e cadastra os imóveis. Pontos vão para o **Ranking COMAC**; quem deixa a ficha recebe o relatório **IPTU atual × potencial** no WhatsApp.

## Como rodar no estande
1. Copie a pasta inteira para o notebook (funciona sem internet).
2. Abra `index.html` no Chrome ou no Edge e aperte `F11` (tela cheia).
3. Clique uma vez na tela para ligar o som e conecte o controle (Xbox ou similar, USB ou Bluetooth).

| | Gamepad | Teclado | Celular/tablet |
|---|---|---|---|
| Pilotar | analógico esquerdo ou direcional | setas ou WASD | arrastar o dedo |
| Turbo | A, RB ou RT | Espaço | botão TURBO |
| Pausa | Start | Esc ou P | — |

**Área da equipe:** ⚙ no canto inferior esquerdo ou `Ctrl+E`. Lá estão a duração do voo (30/45/60/90 s), o prêmio do dia, o som, a planilha de fichas (CSV para o Excel) e o link do relatório de cada ficha (abre o relatório; “Salvar em PDF” e manda no WhatsApp).

As fichas e o ranking ficam no navegador do notebook (localStorage). **Baixe a planilha no fim de cada dia.**

## Regras do jogo
- Bateria de 60 s. Cada marco de área cadastrada (10%, 20%, 35%, 50%, 70% e 90%) dá +3 s.
- Combo: cadastrar sem parar sobe o multiplicador até ×4.
- Casa dourada = “área fora do cadastro”: bônus grande.
- Itens: bateria (+5 s) e sinal FIX (laser dobrado por 6 s). Urubu tira 2 s.
- A pontuação é proporcional à fração da cidade cadastrada, então cidade pequena e cidade grande disputam de igual para igual.

## Dados
| Arquivo | O que é | Como gerar |
|---|---|---|
| `cidades/<código IBGE>.js` | área de voo: edificações em torno do centro urbano | `scripts/gerar_cidades.py` |
| `dados/municipios.js` | lista dos 295 municípios | idem |
| `dados/iptu_sc_siconfi.csv` | IPTU 2025 (2024 se faltar) de cada município | `scripts/siconfi_iptu.py` |
| `dados/casos_recadastramento.json` | casos reais de recadastramento, com fonte | pesquisa manual |
| `dados/iptu.js` | IPTU + comparação por porte + faixa dos casos | `scripts/gerar_iptu.py` |

Cadeia completa (≈ 30 min, precisa de internet só nos 2 primeiros):
```
python scripts/overture_sc.py DADOS/overture_sc.parquet      # edificações Overture (release 2026-10-21.0)
python scripts/ibge_sc.py DADOS                              # Censo 2022, setores e malha
python scripts/cruzar.py DADOS                               # município + urbano/rural de cada edificação
python scripts/gerar_cidades.py DADOS .
python scripts/siconfi_iptu.py
python scripts/gerar_iptu.py .
python scripts/testar_jogo.py . teste Chapec                 # teste no navegador (Playwright)
```

Fontes: Overture Maps Foundation (edificações, inclui Google Open Buildings, Microsoft e OpenStreetMap); IBGE, Censo 2022 e setores censitários; Tesouro Nacional, Siconfi (DCA). O potencial de IPTU é estimativa para conversa, não é lançamento de imposto.
