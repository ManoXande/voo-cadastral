"""Jogadores automáticos do Voo Cadastral: jogam de verdade (gamepad simulado, toque real via CDP ou teclado),
medem o jogo e tiram prints dos momentos-chave.

Uso: playtest.py PASTA_REPO PASTA_SAIDA [perfil ...]
Perfis: leigo-celular, tv-controle, cidade-pequena, cidade-grande, leigo-tv, apressado
Saída: PASTA_SAIDA/<perfil>/ (prints + telemetria.json) e PASTA_SAIDA/resumo_<perfis>.json
"""
import json, math, random, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

RAIZ = Path(sys.argv[1]).resolve()
SAIDA = Path(sys.argv[2]).resolve()
PERFIS = {
    "leigo-celular":  {"tela": (390, 844), "toque": True,  "entrada": "toque",   "cidade": "Xaxim",           "cerebro": "leigo",    "ficha": True},
    "tv-controle":    {"tela": (1920, 1080), "toque": False, "entrada": "pad",   "cidade": "Xanxerê",         "cerebro": "esperto",  "ficha": True},
    "cidade-pequena": {"tela": (1920, 1080), "toque": False, "entrada": "pad",   "cidade": "Santiago do Sul", "cerebro": "esperto",  "ficha": False},
    "cidade-grande":  {"tela": (1920, 1080), "toque": False, "entrada": "pad",   "cidade": "Chapecó",         "cerebro": "esperto",  "ficha": False},
    "leigo-tv":       {"tela": (1920, 1080), "toque": False, "entrada": "pad",   "cidade": "Chapecó",         "cerebro": "leigo",    "ficha": False},
    "apressado":      {"tela": (1366, 768), "toque": False, "entrada": "teclado", "cidade": "Chapecó",        "cerebro": "apressado", "ficha": "abandona"},
}

INIT = """
window.__ft = [];
(function f(t) { if (window.__tA) window.__ft.push(t - window.__tA); window.__tA = t; if (window.__ft.length > 20000) window.__ft.shift(); requestAnimationFrame(f); })(0);
window.__pad = { axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, value: 0 })) };
if (window.__COM_PAD__) navigator.getGamepads = () => [{ id: 'Xbox (simulado)', index: 0, connected: true, mapping: 'standard', axes: window.__pad.axes, buttons: window.__pad.buttons }];
else navigator.getGamepads = () => [];
window.__aperta = (i) => { window.__pad.buttons[i].pressed = true; setTimeout(() => (window.__pad.buttons[i].pressed = false), 140); };
// cérebro "esperto": vai para a célula com mais imóveis não cadastrados, pesando a distância; desvia para itens próximos
window.__alvo = function () {
  const C = J.C, G = C.grade, d = J.drone, E = J.E, nc = G.nc, cel = G.cel;
  for (const p of J.poderes) { const dist = Math.hypot(p.x - d.x, p.y - d.y); if (dist < E.vista * 0.3 && dist > 1) return { x: (p.x - d.x) / dist, y: (p.y - d.y) / dist, turbo: false }; }
  const r = Math.ceil((E.vista * 0.9) / cel), cx = Math.floor(d.x / cel), cy = Math.floor(d.y / cel);
  let best = null, bs = -1;
  for (let l = Math.max(0, cy - r); l <= Math.min(nc - 1, cy + r); l++)
    for (let c = Math.max(0, cx - r); c <= Math.min(nc - 1, cx + r); c++) {
      const k = l * nc + c; let n = 0;
      for (let j = G.ini[k]; j < G.ini[k + 1]; j++) if (!J.feito[G.itens[j]]) n += J.dourado[G.itens[j]] === 1 ? 8 : 1;
      if (!n) continue;
      const px = (c + 0.5) * cel, py = (l + 0.5) * cel, dist = Math.hypot(px - d.x, py - d.y);
      const s = n / (1 + dist / (E.vista * 0.2));
      if (s > bs) { bs = s; best = [px, py, dist]; }
    }
  if (!best) { const dx = C.L / 2 - d.x, dy = C.L / 2 - d.y, m = Math.hypot(dx, dy) || 1; return { x: dx / m, y: dy / m, turbo: true }; }
  const [px, py, dist] = best, m = dist || 1;
  return { x: (px - d.x) / m, y: (py - d.y) / m, turbo: dist > E.vista * 0.25 };
};
window.__foto = function () {
  return { estado: J.estado, tempo: +J.tempo.toFixed(2), decorrido: +J.decorrido.toFixed(2), cad: J.cadastrados, n: J.C ? J.C.n : 0,
    pontos: Math.round(J.pontos), combo: J.combo, marcos: J.marcos.length, dourados: J.dourados, baterias: J.baterias || 0, tonto: J.drone.tonto > 0,
    fix: J.decorrido < J.fixAte, x: J.drone.x, y: J.drone.y, msg: document.querySelector('#hud-msg').classList.contains('on') ? document.querySelector('#hud-msg .m1').textContent : '' };
};
// checagens de interface na tela ativa
window.__ux = function () {
  const tela = document.querySelector('.tela.ativa') || document.querySelector('#hud.ativo');
  const out = { tela: tela ? tela.id : null, vw: innerWidth, vh: innerHeight, problemas: [] };
  if (!tela) return out;
  const pri = tela.querySelector('.btn-pri');
  if (pri) { const r = pri.getBoundingClientRect(); out.ctaVisivelSemRolar = r.top >= 0 && r.bottom <= innerHeight; out.ctaTopo = Math.round(r.top); if (!out.ctaVisivelSemRolar) out.problemas.push(`botão principal "${pri.textContent.trim().slice(0, 40)}" fora da tela (topo em ${Math.round(r.top)} px, tela de ${innerHeight} px)`); }
  let menor = 99, exemplo = '';
  for (const el of tela.querySelectorAll('*')) {
    if (!el.offsetParent || !el.childNodes.length) continue;
    const temTexto = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!temTexto) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0) continue;
    if (r.right > innerWidth + 2 || r.left < -2) out.problemas.push(`texto saindo da tela: "${el.textContent.trim().slice(0, 40)}"`);
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < menor) { menor = fs; exemplo = el.textContent.trim().slice(0, 50); }
  }
  out.menorFonte = menor; out.menorFonteTexto = exemplo;
  if (menor < 11) out.problemas.push(`fonte de ${menor}px: "${exemplo}"`);
  if (document.body.classList.contains('toque')) for (const b of tela.querySelectorAll('button, li[data-i], input')) {
    if (!b.offsetParent) continue; const r = b.getBoundingClientRect();
    if (r.height < 40) out.problemas.push(`alvo de toque pequeno (${Math.round(r.height)} px): "${(b.textContent || b.placeholder || '').trim().slice(0, 30)}"`);
  }
  if (document.documentElement.scrollWidth > innerWidth + 2) out.problemas.push('rolagem horizontal na página');
  return out;
};
"""


def jogar(b, nome, P):
    pasta = SAIDA / nome
    pasta.mkdir(parents=True, exist_ok=True)
    W, H = P["tela"]
    ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=P["toque"], is_mobile=P["toque"], device_scale_factor=2 if P["toque"] else 1)
    pg = ctx.new_page()
    erros, eventos, amostras, ux = [], [], [], {}
    pg.on("console", lambda m: erros.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    cfg = {"duracao": 60, "som": False, "premio": "voo de drone com Raio-X de até 30 ha", "voltarInicio": 12 if P["cerebro"] == "apressado" else 60}
    pg.add_init_script(f"window.__COM_PAD__ = {str(P['entrada'] == 'pad').lower()}; localStorage.setItem('voo-cadastral:config', {json.dumps(json.dumps(cfg))});" + INIT)
    cdp = ctx.new_cdp_session(pg) if P["toque"] else None
    t0 = time.time()
    marca = lambda txt: eventos.append({"t": round(time.time() - t0, 2), "ev": txt})
    foto = lambda arq: pg.screenshot(path=str(pasta / f"{arq}.png"))

    def toque(tipo, x=0, y=0):
        cdp.send("Input.dispatchTouchEvent", {"type": tipo, "touchPoints": [] if tipo == "touchEnd" else [{"x": x, "y": y}]})

    def confirmar():
        if P["entrada"] == "pad": pg.evaluate("__aperta(0)")
        else: pg.keyboard.press("Enter")

    pg.goto(RAIZ.joinpath("index.html").as_uri())
    pg.wait_for_timeout(1800)
    foto("01_inicio"); ux["inicio"] = pg.evaluate("__ux()")
    marca("tela inicial")
    if P["toque"]: pg.tap("#tela-inicio", position={"x": W / 2, "y": H / 2})
    else: confirmar()
    pg.wait_for_timeout(400)
    ux["cidade"] = pg.evaluate("__ux()")
    if P["toque"]: pg.tap("#busca")
    pg.keyboard.type(P["cidade"][:6], delay=140 if P["cerebro"] == "leigo" else 40)
    pg.wait_for_timeout(300)
    foto("02_cidade")
    lista = pg.eval_on_selector_all("#lista-cidades li[data-i]", "ls => ls.map(l => l.querySelector('span').textContent)")
    marca(f"busca '{P['cidade'][:6]}' -> {lista}")
    alvo = next((i for i, n in enumerate(lista) if n == P["cidade"]), 0)
    if P["toque"]:
        pg.tap(f"#lista-cidades li[data-i='{alvo}']")
    else:
        for _ in range(alvo):
            if P["entrada"] == "pad": pg.evaluate("__aperta(13)")
            else: pg.keyboard.press("ArrowDown")
            pg.wait_for_timeout(200)
        confirmar()
    pg.wait_for_timeout(600)
    foto("03_contagem"); ux["contagem"] = pg.evaluate("__ux()")
    marca(f"cidade escolhida: {pg.evaluate('J.C && J.C.nome')}")
    while pg.evaluate("J.estado") == "contagem": pg.wait_for_timeout(100)
    marca("decolou")

    # ---------- o voo ----------
    rnd = random.Random(nome)
    dir_ = (0.0, 0.0); prox_decisao = 0; parado_ate = 0; dedo = None; ultimo_marco = 0; ultimo_tonto = False; fotos_voo = set()
    tvoo = time.time(); abandonou = False
    jx, jy = W * 0.5, H * 0.72
    while True:
        f = pg.evaluate("__foto()")
        amostras.append({**f, "real": round(time.time() - tvoo, 2)})
        if f["estado"] not in ("voo", "pausa"):
            break
        agora = time.time() - tvoo
        if f["marcos"] > ultimo_marco:
            ultimo_marco = f["marcos"]; marca(f"marco {f['marcos']}: {f['msg']}")
            if "marco" not in fotos_voo: fotos_voo.add("marco"); pg.wait_for_timeout(250); foto("05_marco")
        if f["tonto"] and not ultimo_tonto: marca("bateu no urubu")
        ultimo_tonto = f["tonto"]
        for seg, arq in ((4, "04_voo_inicio"), (30, "06_voo_meio"), (55, "07_voo_fim")):
            if agora >= seg and arq not in fotos_voo: fotos_voo.add(arq); foto(arq); ux[arq] = pg.evaluate("__ux()")
        # decide a direção
        if P["cerebro"] == "esperto":
            a = pg.evaluate("__alvo()"); vx, vy, turbo = a["x"], a["y"], a["turbo"]
        elif P["cerebro"] == "leigo":
            if agora >= prox_decisao:
                prox_decisao = agora + rnd.uniform(1.2, 2.2)
                if rnd.random() < 0.2: parado_ate = agora + rnd.uniform(1.0, 2.0)   # "e agora, pra onde?"
                d = pg.evaluate("[J.C.L/2 - J.drone.x, J.C.L/2 - J.drone.y]")
                ang = math.atan2(d[1], d[0]) if rnd.random() < 0.6 else rnd.uniform(0, 2 * math.pi)
                ang += rnd.uniform(-0.6, 0.6)
                dir_ = (math.cos(ang), math.sin(ang))
            vx, vy = (0, 0) if agora < parado_ate else dir_
            turbo = False
        else:  # apressado: voa 10 s em linha e larga o jogo
            if agora < 10: vx, vy, turbo = 1, 0.3, True
            else:
                vx, vy, turbo = 0, 0, False
                if not abandonou: abandonou = True; marca("largou o controle (foi embora)")
        # aplica a entrada
        if P["entrada"] == "pad":
            pg.evaluate(f"__pad.axes[0] = {vx:.3f}; __pad.axes[1] = {vy:.3f}; __pad.buttons[0].pressed = {str(bool(turbo)).lower()}")
        elif P["entrada"] == "toque":
            if vx == 0 and vy == 0:
                if dedo: toque("touchEnd"); dedo = None
            else:
                if not dedo: toque("touchStart", jx, jy); dedo = True
                toque("touchMove", jx + vx * 55, jy + vy * 55)
        else:
            for k, on in (("ArrowRight", vx > 0.3), ("ArrowLeft", vx < -0.3), ("ArrowDown", vy > 0.3), ("ArrowUp", vy < -0.3), ("Space", turbo)):
                pg.keyboard.down(k) if on else pg.keyboard.up(k)
        pg.wait_for_timeout(90)
    if dedo: toque("touchEnd")
    if P["entrada"] == "pad": pg.evaluate("__pad.axes[0] = 0; __pad.axes[1] = 0; __pad.buttons[0].pressed = false")
    marca(f"fim do voo ({amostras[-1]['estado']})")
    while pg.evaluate("J.estado") == "pouso": pg.wait_for_timeout(100)
    pg.wait_for_timeout(700)
    foto("08_fim"); ux["fim"] = pg.evaluate("__ux()")
    if P["toque"]: pg.screenshot(path=str(pasta / "08_fim_pagina_inteira.png"), full_page=True)
    textos_fim = pg.evaluate("({titulo: document.querySelector('#fim-titulo').textContent, resumo: document.querySelector('#fim-resumo').textContent, placar: document.querySelector('#fim-placar').innerText, iptu: document.querySelector('#fim-iptu').innerText})")
    marca("tela de resultado")

    ficha = {}
    if P["ficha"] is True:
        pg.wait_for_timeout(1600)
        tf = time.time()
        if P["toque"]:
            pg.tap("[data-acao=ficha]")
        else:
            confirmar()
        pg.wait_for_timeout(500)
        foto("09_ficha"); ux["ficha"] = pg.evaluate("__ux()")
        campos = [("#f-nome", "Prefeita Maria Teste"), ("#f-whats", "49999719388"), ("#f-trib-nome", "João Tributos"), ("#f-trib-whats", "49988887777")]
        for sel, val in campos:
            if P["toque"]: pg.tap(sel)
            else: pg.click(sel)
            pg.keyboard.type(val, delay=60)
        pg.click("#f-cargo button >> nth=0")
        if P["toque"]: pg.tap("#f-consent")
        else: pg.click("#f-consent")
        foto("10_ficha_preenchida")
        if P["toque"]: pg.tap("[data-acao=salvar-ficha]")
        else: pg.keyboard.press("Enter")
        pg.wait_for_timeout(600)
        ficha = {"segundos_preenchendo": round(time.time() - tf, 1), "estado_depois": pg.evaluate("J.estado"), "erro": pg.inner_text("#ficha-erro")}
        foto("11_ranking"); ux["ranking"] = pg.evaluate("__ux()")
        ficha["titulo_ranking"] = pg.inner_text("#final-titulo")
        marca(f"ficha salva -> {ficha['estado_depois']}")
    elif P["ficha"] == "abandona":
        pg.wait_for_timeout(1600)
        confirmar(); pg.wait_for_timeout(500)
        pg.click("#f-nome"); pg.keyboard.type("Zé", delay=80)
        marca("abriu a ficha, digitou 2 letras e foi embora")
        t1 = time.time()
        while pg.evaluate("J.estado") != "inicio" and time.time() - t1 < 90: pg.wait_for_timeout(500)
        ficha = {"voltou_ao_inicio_em_s": round(time.time() - t1, 1), "estado": pg.evaluate("J.estado")}
        marca(f"tela voltou sozinha para: {ficha['estado']} em {ficha['voltou_ao_inicio_em_s']} s")
        foto("12_voltou_inicio")
    ft = pg.evaluate("__ft.filter(x => x > 0 && x < 1000)")
    ft.sort()
    dados = {
        "perfil": nome, **{k: v for k, v in P.items() if k != "tela"}, "tela": f"{W}x{H}",
        "eventos": eventos, "erros": erros, "ux": ux, "fim": textos_fim, "ficha": ficha,
        "fps_mediana": round(1000 / ft[len(ft) // 2], 1) if ft else None, "quadro_p95_ms": round(ft[int(len(ft) * 0.95)], 1) if ft else None,
        "amostras": amostras,
    }
    (pasta / "telemetria.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    ctx.close()
    return resumir(dados)


def resumir(d):
    a = [x for x in d["amostras"] if x["estado"] == "voo"]
    ult = d["amostras"][-1] if d["amostras"] else {}
    # tempo sem cadastrar nada (janelas de 1 s de jogo sem imóvel novo)
    secos, j = 0, 0
    for i in range(1, len(a)):
        while a[i]["decorrido"] - a[j]["decorrido"] > 1.0: j += 1
        if a[i]["cad"] == a[j]["cad"] and a[i]["decorrido"] - a[j]["decorrido"] > 0.9: secos += a[i]["decorrido"] - a[i - 1]["decorrido"]
    dur = a[-1]["decorrido"] if a else 0
    marcos_t = [round(x["decorrido"], 1) for i, x in enumerate(a) if i and x["marcos"] > a[i - 1]["marcos"]]
    combos = sum(1 for i, x in enumerate(a) if i and x["combo"] > a[i - 1]["combo"])
    real = a[-1]["real"] if a else 0
    return {
        "perfil": d["perfil"], "cidade": d["cidade"], "cerebro": d["cerebro"], "entrada": d["entrada"], "tela": d["tela"],
        "pontos": ult.get("pontos"), "imoveis": ult.get("cad"), "pct_area": round(100 * ult.get("cad", 0) / max(1, ult.get("n", 1)), 1),
        "segundos_de_jogo": round(dur, 1), "segundos_reais": real, "velocidade_jogo": round(dur / real, 2) if real else None,
        "marcos_em_s": marcos_t, "subidas_de_combo": combos, "dourados": ult.get("dourados"), "baterias": max((x.get("baterias", 0) for x in a), default=0),
        "pct_tempo_sem_cadastrar": round(100 * secos / dur, 1) if dur else None,
        "urubus": sum(1 for e in d["eventos"] if "urubu" in e["ev"]),
        "fps_mediana": d["fps_mediana"], "quadro_p95_ms": d["quadro_p95_ms"],
        "problemas_ux": {k: v.get("problemas") for k, v in d["ux"].items() if v.get("problemas")},
        "cta_fim_visivel_sem_rolar": d["ux"].get("fim", {}).get("ctaVisivelSemRolar"),
        "ficha": d["ficha"], "erros": d["erros"], "fim": d["fim"],
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    nomes = sys.argv[3:] or list(PERFIS)
    resumo = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--enable-gpu-rasterization", "--ignore-gpu-blocklist"])
        for n in nomes:
            print("jogando:", n, flush=True)
            try:
                resumo.append(jogar(b, n, PERFIS[n]))
            except Exception as e:  # um perfil quebrado não derruba os outros
                resumo.append({"perfil": n, "falhou": repr(e)})
                print("  FALHOU:", repr(e), flush=True)
        b.close()
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / f"resumo_{'_'.join(nomes)}.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in resumo:
        print(json.dumps({k: v for k, v in r.items() if k not in ("fim", "erros")}, ensure_ascii=False))
