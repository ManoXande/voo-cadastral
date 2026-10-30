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

**Área da equipe:** segure o ⚙ do canto inferior esquerdo por 1 segundo (ou `Ctrl+E`). Lá estão a duração do voo (30/45/60/90 s), o prêmio do dia, o som, a planilha de fichas (CSV para o Excel) e o link do relatório de cada ficha (abre o relatório; “Salvar em PDF” e manda no WhatsApp).

As fichas e o ranking ficam no navegador do notebook (localStorage). **Baixe a planilha no fim de cada dia.**

## Regras do jogo
- Bateria de 60 s. O tempo extra vem das baterias achadas no mapa (+6 s cada); cada marco de área cadastrada (5% a 90%) dá só +1 s. Teto de +20 s (a fila anda). Com menos de 20 s, aparece o aviso e uma bateria perto do drone.
- Cidade 100% cadastrada encerra o voo na hora, com bônus pelo tempo que sobrou. 15 s sem comando encerram o voo.
- Só com o controle, na escolha da cidade: ← → troca a letra inicial, ↑ ↓ anda na lista.
- Combo: cadastrar sem parar sobe o multiplicador até ×4.
- Casa dourada: bônus do jogo (sorteada; não é um achado real).
- Itens: bateria (+6 s) e GPS (sinal FIX: laser dobrado por 6 s). Urubu tira 2 s.
- A pontuação é proporcional à fração da cidade cadastrada, então cidade pequena e cidade grande disputam de igual para igual.
- No resultado: "Você mapeou X% do município" (sobre todas as edificações do município) e a simulação do IPTU com 100% mapeado (IPTU de hoje × o aumento medido nos casos de recadastramento).

## Publicação (GitHub Pages)
O site sai do branch `gh-pages`, não do `main`:
- raiz — v1, congelada como foi publicada em 30/10/2026 (commit `41ae177`): https://manoxande.github.io/voo-cadastral/
- `v2/` — v2: https://manoxande.github.io/voo-cadastral/v2/

O `main` é onde o jogo é desenvolvido. Para atualizar a v2, copie para `v2/` no `gh-pages` os arquivos do jogo do `main` (`index.html`, `jogo.js`, `estilo.css`, `relatorio.html`, `dados/`, `cidades/`, `marca/`).

## Dados
| Arquivo | O que é | Como gerar |
|---|---|---|
| `cidades/<código IBGE>.js` | área de voo: edificações em torno do centro urbano, com ruas, rios, mar, nomes e limites de bairro, prefeitura | `scripts/gerar_cidades.py` |
| `dados/municipios.js` | lista dos 295 municípios | idem |
| `dados/iptu_sc_siconfi.csv` | IPTU 2025 (2024 se faltar) de cada município | `scripts/siconfi_iptu.py` |
| `dados/casos_recadastramento.json` | casos reais de recadastramento, com fonte | pesquisa manual |
| `dados/iptu.js` | IPTU + comparação por porte + faixa dos casos | `scripts/gerar_iptu.py` |

Cadeia completa (≈ 30 min, precisa de internet só nos 2 primeiros):
```
python scripts/overture_sc.py DADOS/overture_sc.parquet      # edificações Overture (release 2026-10-21.0)
python scripts/ibge_sc.py DADOS                              # Censo 2022, setores e malha
python scripts/cruzar.py DADOS                               # município + urbano/rural de cada edificação
python scripts/overture_mapa_sc.py DADOS                     # ruas, água, bairros (Overture) e prefeituras (OSM/Nominatim, ~12 min)
python scripts/gerar_cidades.py DADOS .
python scripts/siconfi_iptu.py
python scripts/gerar_iptu.py .
python scripts/testar_jogo.py . teste Chapec                 # teste no navegador (Playwright)
```

Fontes: Overture Maps Foundation (edificações, inclui Google Open Buildings, Microsoft e OpenStreetMap; ruas, água, bairros e lugares); OpenStreetMap via Nominatim (prefeituras e igrejas matriz); IBGE, Censo 2022 e setores censitários; Tesouro Nacional, Siconfi (DCA). O potencial de IPTU é estimativa para conversa, não é lançamento de imposto.
