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
- Tempo médio do voo escolhido na área da equipe: 45 s, 1 min, 1 min 20 s (padrão) ou 2 min. Bateria inicial, baterias extras, aviso de bateria baixa e reta final escalam juntos (no padrão: bateria de 60 s, baterias de +6 s até +20 s, reta final de 10 s). Os pontos são multiplicados por √(80 s ÷ tempo médio): no playtest, o jogador leigo fez 280 mil, 295 mil e 299 mil pontos em 45 s, 80 s e 2 min. O relógio só começa quando o piloto mexe o controle (ou depois de 4 s). O primeiro item é sempre uma bateria logo à frente.
- O tempo extra vem das baterias achadas no mapa (+6 s cada); cada marco de área cadastrada (4% a 90%) dá só +1 s. Teto de +20 s (a fila anda). Entre 20 s e 10 s, aparece o aviso e uma bateria perto do drone.
- Reta final: nos últimos 10 s os pontos dobram, a borda da tela pulsa, a contagem 5-4-3-2-1 aparece grande e só caem itens de GPS.
- 98% da área de voo encerra o voo na hora, com bônus pelo tempo que sobrou. 15 s sem comando encerram o voo.
- Só com o controle, na escolha da cidade: ← → troca a letra inicial, ↑ ↓ anda na lista.
- Combo: cadastrar sem parar sobe o multiplicador até ×4. A folga entre um telhado e outro cresce nas cidades de casas espalhadas, para elas também chegarem ao ×4.
- Casa dourada: bônus do jogo (sorteada longe da decolagem; não é um achado real). O total das douradas vale o mesmo em qualquer cidade.
- Itens: bateria (+6 s) e GPS (sinal FIX: laser em dobro por 6 s). Item perto do drone é puxado para ele. Urubu tira 2 s.
- Ajuda: depois de ~1 s sem cadastrar, setas saem do drone apontando o que falta (ou a bateria, quando ela está acabando). Quem está abaixo da meta (50% no fim) ganha um laser até 35% mais largo, sem aviso; o piloto bom não recebe.
- A pontuação é proporcional à fração da cidade cadastrada, então cidade pequena e cidade grande disputam de igual para igual.
- Ranking do dia no voo: passar alguém do top 5 aparece sobre o drone; passar o 1º lugar é "Novo recorde do dia!".
- No resultado: 1 a 3 estrelas (área de voo: 45% e 75%), "faltaram X pontos para passar Fulano", "Você mapeou X% do município" (sobre todas as edificações do município) e a simulação do IPTU com 100% mapeado: IPTU de hoje × o aumento medido em recadastramento (Criciúma/SC, +16%, ao lado da média BNDES de 420 municípios, +12,6%), comparado com o de cadastro muito defasado (Mossoró/RN, +39% acima da inflação). Município sem IPTU no Tesouro mostra "dado indisponível" e o ganho medido no caso real.
- O ranking e as fichas da v3 ficam em `voo-cadastral:partidas-v3` no navegador, separados da v1 e da v2 (a escala de pontos mudou).

## Publicação (GitHub Pages)
O site sai do branch `gh-pages`, não do `main`:
- raiz — v1, congelada como foi publicada em 30/10/2026 (commit `41ae177`): https://manoxande.github.io/voo-cadastral/
- `v2/` — v2, congelada como foi publicada em 30/10/2026 (commit `1e7cde7`): https://manoxande.github.io/voo-cadastral/v2/
- `v3/` — v3, acompanha o `main`: https://manoxande.github.io/voo-cadastral/v3/

O `main` é onde o jogo é desenvolvido. Para atualizar a v3, copie para `v3/` no `gh-pages` os arquivos do jogo do `main` (`index.html`, `jogo.js`, `estilo.css`, `relatorio.html`, `dados/`, `cidades/`, `marca/`). As tags `v1`, `v2` e `v3` marcam o commit de cada versão.

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

## Ranking e fichas online

Cada aparelho guarda tudo no navegador e funciona sem internet. Os voos sobem por uma fila para o Supabase (projeto `autha-task`, tabelas `voo_partidas` e `voo_fichas`, esquema em `scripts/web_supabase.sql`), e o ranking do dia junta a TV do estande com os celulares que jogam pelo link. As tabelas ficam fechadas: o jogo só grava e lê o ranking por funções (nome, cargo, município e pontos). WhatsApp e contatos só voltam para a equipe, com a senha da equipe.

Na área da equipe (segure ⚙ por 1 s):
- **Zerar o ranking** tira todos do ranking; as fichas continuam na planilha. Com a senha salva, vale também nos celulares.
- **Apagar voos e fichas deste aparelho** limpa o navegador (baixe a planilha antes); o que já subiu continua no banco.
- **Senha da equipe**: com ela, a planilha traz as fichas feitas pelo link. Para trocar: `update voo_equipe set pin_hash = extensions.crypt('<nova>', extensions.gen_salt('bf'));`

