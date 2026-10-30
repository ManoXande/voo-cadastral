"use strict";
/* Voo Cadastral — Autha-Geo, COMAC-SC 2026.
   Roda direto do arquivo (duplo clique no index.html), sem internet e sem servidor.
   Controles: gamepad (analógico + A = turbo), teclado (setas/WASD + espaço) ou toque (arrasta + botão turbo). */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CHAVE = { partidas: "voo-cadastral:partidas", config: "voo-cadastral:config", ultima: "voo-cadastral:ultima-cidade" };
const CFG_PADRAO = { duracao: 60, som: true, premio: "", voltarInicio: 60 };
const ler = (k, padrao) => { try { return JSON.parse(localStorage.getItem(k)) ?? padrao; } catch { return padrao; } };
const gravar = (k, v) => localStorage.setItem(k, JSON.stringify(v));
let cfg = { ...CFG_PADRAO, ...ler(CHAVE.config, {}) };

const MUN = window.MUNICIPIOS || [];
const MUN_POR_COD = Object.fromEntries(MUN.map((m) => [m.c, m]));
const IPTU = window.IPTU || {};
const CASOS = window.CASOS_RECADASTRO || null;
const CARGOS = ["Prefeito(a)", "Vice-prefeito(a)", "Secretário(a)", "Tributos / fiscal", "Engenharia", "Vereador(a)", "Outro"];

const nf = new Intl.NumberFormat("pt-BR");
const milhar = (n) => nf.format(Math.round(n));
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const hoje = () => new Date().toLocaleDateString("sv-SE");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const digitos = (s) => String(s || "").replace(/\D/g, "");
function reais(v) {
  const um = (x) => x.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  if (v >= 1e9) return "R$ " + um(v / 1e9) + " bi";
  if (v >= 1e6) return "R$ " + um(v / 1e6) + " mi";
  if (v >= 1e3) return "R$ " + milhar(v / 1e3) + " mil";
  return "R$ " + milhar(v);
}

/* ============================== som (sintetizado, sem arquivos) ============================== */
const Som = (() => {
  let ctx = null, mestre = null, motor = null;
  function garantir() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!ctx) { ctx = new AC(); mestre = ctx.createGain(); mestre.gain.value = 0.32; mestre.connect(ctx.destination); }
    if (ctx.state === "suspended") ctx.resume();
  }
  const pronto = () => cfg.som && ctx && ctx.state === "running";
  function tom(freq, dur = 0.08, tipo = "square", vol = 0.2, quando = 0, deslize = 0) {
    if (!pronto()) return;
    const t = ctx.currentTime + quando, o = ctx.createOscillator(), g = ctx.createGain();
    o.type = tipo;
    o.frequency.setValueAtTime(freq, t);
    if (deslize) o.frequency.exponentialRampToValueAtTime(Math.max(40, freq + deslize), t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.006);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(mestre); o.start(t); o.stop(t + dur + 0.03);
  }
  let ultimoTick = 0;
  return {
    garantir,
    ativo: () => !!ctx && ctx.state === "running",
    tick(combo) {
      const t = performance.now();
      if (t - ultimoTick < 40) return;
      ultimoTick = t;
      tom(620 + combo * 130 + Math.random() * 80, 0.035, "square", 0.06);
    },
    dourado() { [880, 1175, 1568, 2093].forEach((f, i) => tom(f, 0.14, "triangle", 0.22, i * 0.055)); },
    poder() { [523, 659, 784, 1047].forEach((f, i) => tom(f, 0.1, "square", 0.14, i * 0.05)); },
    marco() { [523, 659, 784].forEach((f) => tom(f, 0.55, "triangle", 0.16)); tom(1047, 0.7, "triangle", 0.2, 0.16); },
    batida() { tom(220, 0.35, "sawtooth", 0.25, 0, -150); tom(90, 0.3, "square", 0.15); },
    contagem(final) { tom(final ? 1047 : 587, final ? 0.45 : 0.16, "square", 0.2); },
    alerta() { tom(1500, 0.06, "square", 0.12); },
    fim() { [784, 659, 523, 784, 1047].forEach((f, i) => tom(f, 0.24, "triangle", 0.2, i * 0.12)); },
    clique() { tom(1250, 0.025, "square", 0.06); },
    motorLiga() {
      if (!pronto() || motor) return;
      const o = ctx.createOscillator(), o2 = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      o.type = "sawtooth"; o2.type = "sawtooth"; o.frequency.value = 118; o2.frequency.value = 121;
      f.type = "lowpass"; f.frequency.value = 650; g.gain.value = 0.0001;
      o.connect(f); o2.connect(f); f.connect(g); g.connect(mestre); o.start(); o2.start();
      g.gain.exponentialRampToValueAtTime(0.05, ctx.currentTime + 0.4);
      motor = { o, o2, g };
    },
    motorVel(v) { if (motor) { const t = ctx.currentTime; motor.o.frequency.setTargetAtTime(118 + v * 70, t, 0.1); motor.o2.frequency.setTargetAtTime(121 + v * 74, t, 0.1); } },
    motorDesliga() {
      if (!motor) return;
      const m = motor; motor = null;
      m.g.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.15);
      setTimeout(() => { m.o.stop(); m.o2.stop(); }, 700);
    },
  };
})();

/* ============================== entrada: gamepad, teclado, toque ============================== */
const Ent = { teclas: new Set(), joy: null, turboToque: false, pad: { x: 0, y: 0, turbo: false }, padAnt: [], navAnt: { x: 0, y: 0 }, tipo: "teclado" };
let ultimaAtividade = performance.now();
const atividade = () => { ultimaAtividade = performance.now(); };

function lerPad() {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  let p = null;
  for (const g of pads) if (g && g.connected) { p = g; break; }
  if (!p) { Ent.pad.x = Ent.pad.y = 0; Ent.pad.turbo = false; return; }
  const b = (i) => !!(p.buttons[i] && p.buttons[i].pressed);
  let x = p.axes[0] || 0, y = p.axes[1] || 0;
  const m = Math.hypot(x, y), MORTA = 0.18;
  if (m < MORTA) { x = y = 0; } else { const k = Math.min(1, (m - MORTA) / (1 - MORTA)) / m; x *= k; y *= k; }
  if (b(12)) y = -1; if (b(13)) y = 1; if (b(14)) x = -1; if (b(15)) x = 1;
  Ent.pad.x = x; Ent.pad.y = y;
  Ent.pad.turbo = b(0) || b(5) || b(7);
  const agora = p.buttons.map((bt) => bt.pressed);
  const mapa = { 0: "confirmar", 1: "voltar", 2: "x", 3: "y", 9: "start", 12: "cima", 13: "baixo", 14: "esquerda", 15: "direita" };
  agora.forEach((v, i) => { if (v && !Ent.padAnt[i] && mapa[i]) { Ent.tipo = "pad"; acao(mapa[i]); } });
  // analógico também navega nos menus (só na borda: empurrou além de 0,6)
  const nx = Math.abs(p.axes[0]) > 0.6 ? Math.sign(p.axes[0]) : 0, ny = Math.abs(p.axes[1]) > 0.6 ? Math.sign(p.axes[1]) : 0;
  if (J.estado !== "voo" && J.estado !== "contagem") {
    if (ny && ny !== Ent.navAnt.y) acao(ny < 0 ? "cima" : "baixo");
    if (nx && nx !== Ent.navAnt.x) acao(nx < 0 ? "esquerda" : "direita");
  }
  Ent.navAnt = { x: nx, y: ny };
  if (agora.some(Boolean) || m > 0.4) { Ent.tipo = "pad"; atividade(); }
  Ent.padAnt = agora;
}

function vetorEntrada() {
  let x = Ent.pad.x, y = Ent.pad.y;
  const t = Ent.teclas;
  if (t.has("ArrowLeft") || t.has("KeyA")) x -= 1;
  if (t.has("ArrowRight") || t.has("KeyD")) x += 1;
  if (t.has("ArrowUp") || t.has("KeyW")) y -= 1;
  if (t.has("ArrowDown") || t.has("KeyS")) y += 1;
  if (Ent.joy) { x += Ent.joy.vx; y += Ent.joy.vy; }
  const m = Math.hypot(x, y);
  if (m > 1) { x /= m; y /= m; }
  const turbo = Ent.pad.turbo || t.has("Space") || t.has("ShiftLeft") || t.has("ShiftRight") || Ent.turboToque;
  return { x, y, turbo };
}

const NAO_E_TEXTO = (e) => !(e.target instanceof HTMLInputElement) || e.target.type === "checkbox";
addEventListener("keydown", (e) => {
  Som.garantir(); atividade();
  if (e.ctrlKey && (e.key === "e" || e.key === "E")) { e.preventDefault(); abrirEquipe(); return; }
  if ($("#equipe").classList.contains("ativo")) { if (e.key === "Escape") fecharEquipe(); return; }
  if (NAO_E_TEXTO(e)) { Ent.teclas.add(e.code); Ent.tipo = "teclado"; }
  const emJogo = J.estado === "voo" || J.estado === "contagem";
  if (emJogo && ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.code)) e.preventDefault();
  const mapa = { Enter: "confirmar", Escape: "voltar", ArrowUp: "cima", ArrowDown: "baixo", ArrowLeft: "esquerda", ArrowRight: "direita" };
  if (e.key === "p" || e.key === "P") { if (NAO_E_TEXTO(e)) acao("start"); return; }
  if (e.repeat && e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
  if (mapa[e.key]) {
    // dentro de campo de texto, setas esquerda/direita andam no texto
    if (!NAO_E_TEXTO(e) && (e.key === "ArrowLeft" || e.key === "ArrowRight")) return;
    if (J.estado === "cidade" || J.estado === "ficha" || !emJogo) e.preventDefault();
    acao(mapa[e.key]);
  } else if (NAO_E_TEXTO(e) && (e.key === "y" || e.key === "Y" || e.key === "r" || e.key === "R")) acao("y");
  else if (NAO_E_TEXTO(e) && (e.key === "x" || e.key === "X")) acao("x");
});
addEventListener("keyup", (e) => Ent.teclas.delete(e.code));
addEventListener("blur", () => { Ent.teclas.clear(); if (J.estado === "voo") pausar(true); });
document.addEventListener("visibilitychange", () => { if (document.hidden && J.estado === "voo") pausar(true); });
addEventListener("pointerdown", (e) => {
  if (e.pointerType === "touch") document.body.classList.add("toque");
  Som.garantir(); atividade(); setTimeout(atualizarAvisoSom, 100);
}, true);
addEventListener("gamepadconnected", () => { Ent.tipo = "pad"; atualizarCTA(); });

// joystick flutuante: encosta o dedo (ou o mouse) em qualquer lugar da tela do voo e arrasta
const canvas = $("#tela");
canvas.addEventListener("pointerdown", (e) => {
  if (e.pointerType === "touch") document.body.classList.add("toque");
  if (J.estado === "inicio") { acao("confirmar"); return; }
  if (J.estado !== "voo" && J.estado !== "contagem") return;
  Ent.tipo = e.pointerType === "touch" ? "toque" : "mouse";
  Ent.joy = { id: e.pointerId, x0: e.clientX, y0: e.clientY, vx: 0, vy: 0 };
  const j = $("#joy"); j.style.display = "block"; j.style.left = e.clientX + "px"; j.style.top = e.clientY + "px";
  $("#joy i").style.transform = "";
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove", (e) => {
  if (!Ent.joy || e.pointerId !== Ent.joy.id) return;
  const R = 60, dx = e.clientX - Ent.joy.x0, dy = e.clientY - Ent.joy.y0, m = Math.hypot(dx, dy);
  const k = m > R ? R / m : 1;
  Ent.joy.vx = (dx * k) / R; Ent.joy.vy = (dy * k) / R;
  $("#joy i").style.transform = `translate(${dx * k}px, ${dy * k}px)`;
});
const soltarJoy = (e) => { if (Ent.joy && e.pointerId === Ent.joy.id) { Ent.joy = null; $("#joy").style.display = "none"; } };
canvas.addEventListener("pointerup", soltarJoy);
canvas.addEventListener("pointercancel", soltarJoy);
const turbo = $("#btn-turbo");
turbo.addEventListener("pointerdown", (e) => { e.stopPropagation(); Ent.turboToque = true; });
["pointerup", "pointercancel", "pointerleave"].forEach((ev) => turbo.addEventListener(ev, () => (Ent.turboToque = false)));

/* ============================== cidade: carga e estrutura espacial ============================== */
const esperas = {};
window.carregarCidade = (c) => { if (esperas[c.c]) esperas[c.c](c); };
const cacheCidades = new Map();

function abrirCidade(cod) {
  if (cacheCidades.has(cod)) return Promise.resolve(cacheCidades.get(cod));
  return new Promise((ok, falha) => {
    const s = document.createElement("script");
    esperas[cod] = (c) => { delete esperas[cod]; const C = montarCidade(c); cacheCidades.clear(); cacheCidades.set(cod, C); ok(C); };
    s.onerror = () => falha(new Error("mapa não encontrado"));
    s.src = `cidades/${cod}.js`;
    document.body.appendChild(s);
    s.onload = () => s.remove();
  });
}

function montarCidade(c) {
  const bin = atob(c.b), n = bin.length / 5, L = c.lado;
  const bx = new Float32Array(n), by = new Float32Array(n), bs = new Float32Array(n);
  for (let i = 0, o = 0; i < n; i++, o += 5) {
    bx[i] = ((bin.charCodeAt(o) | (bin.charCodeAt(o + 1) << 8)) / 65535) * L;
    by[i] = ((bin.charCodeAt(o + 2) | (bin.charCodeAt(o + 3) << 8)) / 65535) * L;
    bs[i] = bin.charCodeAt(o + 4) / 5;
  }
  // grade de busca (CSR): célula -> lista de edificações
  const nc = 96, cel = L / nc, ini = new Uint32Array(nc * nc + 1), qual = new Uint32Array(n);
  for (let i = 0; i < n; i++) {
    const k = Math.min(nc - 1, (by[i] / cel) | 0) * nc + Math.min(nc - 1, (bx[i] / cel) | 0);
    qual[i] = k; ini[k + 1]++;
  }
  for (let k = 0; k < nc * nc; k++) ini[k + 1] += ini[k];
  const cursor = ini.slice(0, nc * nc), itens = new Uint32Array(n);
  for (let i = 0; i < n; i++) itens[cursor[qual[i]]++] = i;
  return { ...c, nome: c.n, b: null, n, L, bx, by, bs, grade: { nc, cel, ini, itens } };   // n = nº de edificações
}

/* ============================== camadas desenhadas uma vez (fora da tela) ============================== */
const GROSSO = matchMedia("(pointer: coarse)").matches;
const TAM = GROSSO ? 2048 : 4096, TAM_RASTRO = 1024;
const cvPredios = document.createElement("canvas"); cvPredios.width = cvPredios.height = TAM;
const cvRastro = document.createElement("canvas"); cvRastro.width = cvRastro.height = TAM_RASTRO;
const ctxP = cvPredios.getContext("2d"), ctxR = cvRastro.getContext("2d");
const COR = { predio: "#34425a", feito: "#4ddf84", ouro: "#fbbf24", limite: "rgba(92,215,179,.55)" };

function desenharBase(C) {
  const k = TAM / C.L;
  ctxP.clearRect(0, 0, TAM, TAM);
  ctxR.clearRect(0, 0, TAM_RASTRO, TAM_RASTRO);
  ctxP.strokeStyle = COR.limite; ctxP.lineWidth = Math.max(2, TAM / 900); ctxP.lineJoin = "round";
  for (const anel of C.limite) {
    ctxP.beginPath();
    anel.forEach(([x, y], i) => (i ? ctxP.lineTo(x * TAM, y * TAM) : ctxP.moveTo(x * TAM, y * TAM)));
    ctxP.stroke();
  }
  ctxP.fillStyle = COR.predio;
  for (let i = 0; i < C.n; i++) quadrado(C, i, k);
}
function quadrado(C, i, k) {
  const s = Math.max(1.3, C.bs[i] * k * 0.86);
  ctxP.fillRect(C.bx[i] * k - s / 2, C.by[i] * k - s / 2, s, s);
}

/* ============================== estado do jogo ============================== */
const J = {
  estado: "inicio", C: null, demo: false,
  drone: { x: 0, y: 0, vx: 0, vy: 0, ang: -Math.PI / 2, alt: 1, tonto: 0 },
  cam: { x: 0, y: 0 },
  feito: null, dourado: null, douradosLista: [],
  tempo: 60, decorrido: 0, pontos: 0, cadastrados: 0, dourados: 0,
  combo: 1, comboT: 0, ultimoAchado: -9, marcos: [], fixAte: 0,
  poderes: [], urubus: [], part: [], textos: [], proximoPoder: 4, proximoUrubu: 9,
  msgAte: 0, contagemT: 0, pousoT: 0, resultado: null, partidaId: null, alertaSeg: 99,
};
const MARCOS = [
  { p: 0.10, t: "Base cartográfica no ar", s: "o laser já desenha a cidade" },
  { p: 0.20, t: "Área construída medida", s: "cada telhado com a sua metragem" },
  { p: 0.35, t: "Cadastro × tributário", s: "aparece o que não estava lançado" },
  { p: 0.50, t: "Meia cidade cadastrada!", s: "imóveis prontos para o CIB" },
  { p: 0.70, t: "Planta de valores com base no mapa", s: "decisão justificada, sem achismo" },
  { p: 0.90, t: "Cidade quase inteira!", s: "o cadastro mais completo da COMAC" },
];
const BONUS_MARCO = 3;

// escala da cidade: tudo é proporcional ao tamanho da área de voo, para cidade pequena e grande serem igualmente jogáveis
function escalaVoo(C) {
  const vista = C.L * 0.42;              // metros visíveis no menor lado da tela
  return { vista, vel: vista / 2.7, raio: vista * 0.065, pontoBase: 100000 / C.n };
}

function prepararPartida(C, demo) {
  J.C = C; J.demo = demo;
  J.E = escalaVoo(C);
  J.feito = new Uint8Array(C.n);
  J.dourado = new Uint8Array(C.n);
  J.douradosLista = [];
  const nOuro = clamp(Math.round(C.n * 0.006), 6, 160);
  // dourados: imóveis "com área construída fora do cadastro", preferindo os maiores
  for (let t = 0; t < nOuro * 6 && J.douradosLista.length < nOuro; t++) {
    const i = (Math.random() * C.n) | 0;
    if (!J.dourado[i] && C.bs[i] > 7) { J.dourado[i] = 1; J.douradosLista.push(i); }
  }
  desenharBase(C);
  // decola do pico urbano (centro da área de voo)
  Object.assign(J.drone, { x: C.L / 2, y: C.L / 2, vx: 0, vy: 0, ang: -Math.PI / 2, alt: demo ? 1 : 0, tonto: 0 });
  J.cam.x = J.drone.x; J.cam.y = J.drone.y;
  Object.assign(J, {
    tempo: cfg.duracao, decorrido: 0, pontos: 0, cadastrados: 0, dourados: 0, combo: 1, comboT: 0, ultimoAchado: -9,
    marcos: [], fixAte: 0, poderes: [], urubus: [], part: [], textos: [], proximoPoder: 3.5, proximoUrubu: 9, msgAte: 0, alertaSeg: 99,
  });
  J.demoAlvo = { t: Math.random() * 100 };
}

/* ============================== laço principal ============================== */
let ultimoT = performance.now();
function quadro(t) {
  const dt = Math.min(0.05, (t - ultimoT) / 1000);
  ultimoT = t;
  lerPad();
  if (J.estado === "voo") atualizarVoo(dt);
  else if (J.estado === "contagem") atualizarContagem(dt);
  else if (J.estado === "pouso") atualizarPouso(dt);
  else if (J.demo && J.C && J.estado === "inicio") atualizarDemo(dt);
  if (J.C) desenhar(t / 1000);
  verificarInatividade();
  requestAnimationFrame(quadro);
}

function moverDrone(dt, entrada) {
  const d = J.drone, E = J.E;
  let ix = entrada.x, iy = entrada.y;
  if (d.tonto > 0) { d.tonto -= dt; ix = Math.cos(d.tonto * 18) * 0.5; iy = Math.sin(d.tonto * 18) * 0.5; }
  const vmax = E.vel * (entrada.turbo ? 1.55 : 1);
  const tx = ix * vmax, ty = iy * vmax, a = Math.min(1, dt * 4.5);
  d.vx += (tx - d.vx) * a; d.vy += (ty - d.vy) * a;
  const px = d.x, py = d.y;
  d.x = clamp(d.x + d.vx * dt, 0, J.C.L); d.y = clamp(d.y + d.vy * dt, 0, J.C.L);
  const v = Math.hypot(d.vx, d.vy);
  if (v > E.vel * 0.08) {
    const alvo = Math.atan2(d.vy, d.vx);
    let dif = alvo - d.ang;
    while (dif > Math.PI) dif -= 2 * Math.PI;
    while (dif < -Math.PI) dif += 2 * Math.PI;
    d.ang += dif * Math.min(1, dt * 8);
  }
  // câmera segue o drone, olhando um pouco à frente
  const ac = Math.min(1, dt * 3.2);
  J.cam.x += (d.x + d.vx * 0.45 - J.cam.x) * ac;
  J.cam.y += (d.y + d.vy * 0.45 - J.cam.y) * ac;
  return { px, py, v };
}

function atualizarVoo(dt) {
  const ent = vetorEntrada();
  const { px, py, v } = moverDrone(dt, ent);
  Som.motorVel(v / J.E.vel);
  J.decorrido += dt;
  J.tempo -= dt;
  escanear(px, py, J.drone.x, J.drone.y, dt);
  atualizarPoderes(dt);
  atualizarUrubus(dt);
  atualizarParticulas(dt);
  const seg = Math.ceil(J.tempo);
  if (seg <= 5 && seg !== J.alertaSeg && seg > 0) { J.alertaSeg = seg; Som.alerta(); }
  if (J.tempo <= 0) { J.tempo = 0; iniciarPouso(); }
  if (J.decorrido > 4.5) $("#hud-ajuda").classList.add("some");
  atualizarHUD();
}

function atualizarDemo(dt) {
  // piloto automático: persegue um alvo que passeia em curva de Lissajous pela área central
  const C = J.C, a = J.demoAlvo;
  a.t += dt;
  const ax = C.L * (0.5 + 0.28 * Math.sin(a.t * 0.23)), ay = C.L * (0.5 + 0.28 * Math.sin(a.t * 0.31 + 1));
  const dx = ax - J.drone.x, dy = ay - J.drone.y, m = Math.hypot(dx, dy) || 1;
  const { px, py } = moverDrone(dt, { x: (dx / m) * 0.7, y: (dy / m) * 0.7, turbo: false });
  escanear(px, py, J.drone.x, J.drone.y, dt);
  atualizarParticulas(dt);
  if (J.cadastrados > C.n * 0.45) { prepararPartida(C, true); }
}

function atualizarContagem(dt) {
  const antes = Math.ceil(J.contagemT);
  J.contagemT -= dt;
  J.drone.alt = clamp(1 - J.contagemT / 3, 0, 1);
  const agora = Math.ceil(J.contagemT);
  const el = $("#contagem");
  if (J.contagemT <= 0) {
    el.textContent = "";
    J.estado = "voo";
    J.drone.alt = 1;
    Som.motorLiga();
    return;
  }
  if (agora !== antes) { el.textContent = agora > 0 ? agora : ""; Som.contagem(false); }
  if (J.contagemT < 0.6 && el.textContent !== "DECOLAR!") { el.textContent = "DECOLAR!"; Som.contagem(true); }
}

function iniciarPouso() {
  J.estado = "pouso"; J.pousoT = 1.6;
  Som.motorDesliga(); Som.fim();
  mensagem("Bateria no fim", "pousando o drone…", "");
}
function atualizarPouso(dt) {
  J.pousoT -= dt;
  const d = J.drone;
  d.vx *= 0.9; d.vy *= 0.9; d.alt = clamp(J.pousoT / 1.6, 0, 1);
  atualizarParticulas(dt);
  if (J.pousoT <= 0) mostrarFim();
}

/* ---------- o laser cadastral ---------- */
function escanear(x1, y1, x2, y2, dt) {
  const C = J.C, E = J.E, G = C.grade;
  const fix = J.decorrido < J.fixAte;
  const r = E.raio * (fix ? 1.8 : 1);
  const minx = Math.min(x1, x2) - r - 40, maxx = Math.max(x1, x2) + r + 40;
  const miny = Math.min(y1, y2) - r - 40, maxy = Math.max(y1, y2) + r + 40;
  const c0 = clamp((minx / G.cel) | 0, 0, G.nc - 1), c1 = clamp((maxx / G.cel) | 0, 0, G.nc - 1);
  const l0 = clamp((miny / G.cel) | 0, 0, G.nc - 1), l1 = clamp((maxy / G.cel) | 0, 0, G.nc - 1);
  const sx = x2 - x1, sy = y2 - y1, s2 = sx * sx + sy * sy || 1e-9;
  const k = TAM / C.L;
  let achados = 0, ouro = 0, pontosAqui = 0;
  ctxP.fillStyle = COR.feito;
  for (let l = l0; l <= l1; l++) {
    for (let c = c0; c <= c1; c++) {
      const cel = l * G.nc + c;
      for (let j = G.ini[cel], fim = G.ini[cel + 1]; j < fim; j++) {
        const i = G.itens[j];
        if (J.feito[i]) continue;
        const bx = C.bx[i], by = C.by[i];
        let t = ((bx - x1) * sx + (by - y1) * sy) / s2;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
        const dx = bx - (x1 + sx * t), dy = by - (y1 + sy * t), rr = r + C.bs[i] * 0.4;
        if (dx * dx + dy * dy > rr * rr) continue;
        J.feito[i] = 1;
        achados++;
        quadrado(C, i, k);
        if (J.dourado[i]) { ouro++; J.dourado[i] = 2; poeira(bx, by, "ouro"); }
        else if (achados <= 30 && Math.random() < 0.5) poeira(bx, by, "verde");
      }
    }
  }
  // rastro: a faixa já varrida pelo laser
  const kr = TAM_RASTRO / C.L;
  ctxR.strokeStyle = "#4ddf84"; ctxR.lineCap = "round"; ctxR.lineWidth = 2 * r * kr;
  ctxR.beginPath(); ctxR.moveTo(x1 * kr, y1 * kr); ctxR.lineTo(x2 * kr + 0.01, y2 * kr); ctxR.stroke();
  if (J.demo) { J.cadastrados += achados; return; }
  // combo: cadastrar sem parar sobe o multiplicador
  if (achados) { J.comboT += dt; J.ultimoAchado = J.decorrido; }
  else if (J.decorrido - J.ultimoAchado > 1.6) J.comboT = 0;
  const novoCombo = J.comboT >= 7 ? 4 : J.comboT >= 4 ? 3 : J.comboT >= 2 ? 2 : 1;
  if (novoCombo > J.combo) { Som.poder(); flutuar(J.drone.x, J.drone.y, `COMBO ×${novoCombo}`, "#fbbf24", 1.4); }
  J.combo = novoCombo;
  if (achados) {
    pontosAqui = achados * E.pontoBase * J.combo;
    J.cadastrados += achados;
    Som.tick(J.combo);
  }
  if (ouro) {
    const bonus = ouro * (E.pontoBase * 15 + 250) * J.combo;
    pontosAqui += bonus;
    J.dourados += ouro;
    Som.dourado();
    flutuar(J.drone.x, J.drone.y - E.raio * 0.6, `Área fora do cadastro! +${milhar(bonus)}`, "#fbbf24", 1.6);
  }
  J.pontos += pontosAqui;
  verificarMarcos();
}

function verificarMarcos() {
  const p = J.cadastrados / J.C.n;
  for (const m of MARCOS) {
    if (p >= m.p && !J.marcos.includes(m.p)) {
      J.marcos.push(m.p);
      J.tempo += BONUS_MARCO;
      Som.marco();
      const pot = potencial(J.C.c);
      const extra = !pot ? "" : pot.ganhoMax > pot.ganhoMin ? `Receita potencial: +${reais(pot.ganhoMin * p)} a ${reais(pot.ganhoMax * p)}/ano` : `Receita potencial: +${reais(pot.ganhoMin * p)}/ano`;
      mensagem(`${Math.round(m.p * 100)}% · ${m.t}`, `${m.s} · +${BONUS_MARCO} s de bateria`, extra);
    }
  }
}

/* ---------- itens: bateria, sinal FIX (laser largo) ---------- */
function atualizarPoderes(dt) {
  const E = J.E, d = J.drone;
  J.proximoPoder -= dt;
  if (J.proximoPoder <= 0 && J.poderes.length < 3) {
    J.proximoPoder = 5 + Math.random() * 3;
    // nasce à frente do drone, sobre uma edificação ainda não cadastrada se possível
    const dist = E.vista * (0.28 + Math.random() * 0.2), ang = d.ang + (Math.random() - 0.5) * 2.2;
    let x = clamp(d.x + Math.cos(ang) * dist, E.raio, J.C.L - E.raio), y = clamp(d.y + Math.sin(ang) * dist, E.raio, J.C.L - E.raio);
    J.poderes.push({ x, y, tipo: Math.random() < 0.55 ? "bateria" : "fix", vida: 11 });
  }
  for (const p of J.poderes) {
    p.vida -= dt;
    if (Math.hypot(p.x - d.x, p.y - d.y) < E.vista * 0.06) {
      p.vida = -1;
      Som.poder();
      if (p.tipo === "bateria") { J.tempo += 5; flutuar(p.x, p.y, "+5 s de bateria", "#4ddf84", 1.3); }
      else { J.fixAte = J.decorrido + 6; flutuar(p.x, p.y, "Sinal FIX: laser dobrado!", "#5cd7b3", 1.5); }
      for (let k = 0; k < 14; k++) poeira(p.x, p.y, p.tipo === "bateria" ? "verde" : "menta");
    }
  }
  J.poderes = J.poderes.filter((p) => p.vida > 0);
}

/* ---------- urubus: obstáculo leve ---------- */
function atualizarUrubus(dt) {
  const E = J.E, d = J.drone;
  J.proximoUrubu -= dt;
  if (J.proximoUrubu <= 0 && J.urubus.length < 2 && J.decorrido > 6) {
    J.proximoUrubu = 7 + Math.random() * 5;
    const lado = Math.random() < 0.5 ? -1 : 1, y = d.y + (Math.random() - 0.5) * E.vista * 0.7;
    J.urubus.push({ x: d.x - lado * E.vista * 0.9, y, vx: lado * E.vel * 0.42, vy: (Math.random() - 0.5) * E.vel * 0.15, vida: 9, fase: Math.random() * 6 });
  }
  for (const u of J.urubus) {
    u.x += u.vx * dt; u.y += u.vy * dt; u.vida -= dt; u.fase += dt * 9;
    if (!u.bateu && d.tonto <= 0 && Math.hypot(u.x - d.x, u.y - d.y) < E.vista * 0.045) {
      u.bateu = true; d.tonto = 0.9; J.tempo = Math.max(0.5, J.tempo - 2); J.comboT = 0;
      Som.batida(); flutuar(d.x, d.y, "Urubu! −2 s", "#f87171", 1.3);
    }
  }
  J.urubus = J.urubus.filter((u) => u.vida > 0);
}

/* ---------- partículas e textos ---------- */
function poeira(x, y, tipo) {
  if (J.part.length > 500) return;
  const a = Math.random() * Math.PI * 2, v = J.E.vista * (0.02 + Math.random() * 0.06);
  J.part.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vida: 0.6 + Math.random() * 0.5, max: 1.1, tipo });
}
function flutuar(x, y, txt, cor, dur) { J.textos.push({ x, y, txt, cor, vida: dur, max: dur }); }
function atualizarParticulas(dt) {
  for (const p of J.part) { p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.94; p.vy *= 0.94; p.vida -= dt; }
  J.part = J.part.filter((p) => p.vida > 0);
  for (const t of J.textos) { t.vida -= dt; t.y -= J.E.vista * 0.05 * dt; }
  J.textos = J.textos.filter((t) => t.vida > 0);
}

/* ============================== desenho ============================== */
const ctx = canvas.getContext("2d");
let W = 0, H = 0, DPR = 1;
function redimensionar() {
  DPR = Math.min(2, window.devicePixelRatio || 1);
  W = Math.round(innerWidth * DPR); H = Math.round(innerHeight * DPR);
  canvas.width = W; canvas.height = H;
}
addEventListener("resize", redimensionar);
redimensionar();

function passoGrade(vista) {
  const alvo = vista / 6;
  for (const p of [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000]) if (p >= alvo) return p;
  return 10000;
}

function desenhar(tempo) {
  const C = J.C, E = J.E, d = J.drone;
  const esc = Math.min(W, H) / E.vista;                  // pixels por metro
  const ox = W / 2 - J.cam.x * esc, oy = H / 2 - J.cam.y * esc;
  const sx = (x) => ox + x * esc, sy = (y) => oy + y * esc;

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = "#030712";
  ctx.fillRect(0, 0, W, H);
  // área de voo (fora dela fica mais escuro)
  ctx.fillStyle = "#060c1a";
  ctx.fillRect(sx(0), sy(0), C.L * esc, C.L * esc);

  // grade UTM (SIRGAS 2000 / UTM 22S)
  const passo = passoGrade(E.vista);
  ctx.strokeStyle = "rgba(148,163,184,.07)"; ctx.lineWidth = 1;
  ctx.fillStyle = "rgba(148,163,184,.35)"; ctx.font = `${Math.round(11 * DPR)}px Consolas, monospace`;
  const eIni = Math.ceil((C.x0 + (J.cam.x - W / 2 / esc)) / passo) * passo;
  for (let e = eIni; e < C.x0 + J.cam.x + W / 2 / esc; e += passo) {
    const x = sx(e - C.x0);
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    ctx.fillText("E " + milhar(e), x + 4 * DPR, H - 6 * DPR);
  }
  const nTopo = C.y0 + C.L - (J.cam.y - H / 2 / esc);
  for (let nn = Math.floor(nTopo / passo) * passo; nn > nTopo - H / esc; nn -= passo) {
    const y = sy(C.y0 + C.L - nn);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    ctx.fillText("N " + milhar(nn), 4 * DPR, y - 4 * DPR);
  }

  // rastro do laser + edificações (camadas prontas, recortadas na vista)
  ctx.imageSmoothingEnabled = true;
  ctx.globalAlpha = 0.09;
  ctx.drawImage(cvRastro, sx(0), sy(0), C.L * esc, C.L * esc);
  ctx.globalAlpha = 1;
  const kP = TAM / C.L;
  const vx0 = clamp(J.cam.x - W / 2 / esc, 0, C.L), vy0 = clamp(J.cam.y - H / 2 / esc, 0, C.L);
  const vx1 = clamp(J.cam.x + W / 2 / esc, 0, C.L), vy1 = clamp(J.cam.y + H / 2 / esc, 0, C.L);
  if (vx1 > vx0 && vy1 > vy0) {
    ctx.imageSmoothingEnabled = esc < kP;
    ctx.drawImage(cvPredios, vx0 * kP, vy0 * kP, (vx1 - vx0) * kP, (vy1 - vy0) * kP, sx(vx0), sy(vy0), (vx1 - vx0) * esc, (vy1 - vy0) * esc);
  }

  // dourados ainda não achados brilham (só os que estão na vista)
  const pulso = 0.55 + 0.45 * Math.sin(tempo * 5);
  ctx.fillStyle = COR.ouro;
  for (const i of J.douradosLista) {
    if (J.dourado[i] !== 1) continue;
    const x = sx(C.bx[i]), y = sy(C.by[i]);
    if (x < -50 || y < -50 || x > W + 50 || y > H + 50) continue;
    const s = Math.max(5 * DPR, C.bs[i] * esc * 0.9);
    ctx.globalAlpha = 0.25 * pulso; ctx.beginPath(); ctx.arc(x, y, s * 1.6 + 6 * DPR, 0, 7); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillRect(x - s / 2, y - s / 2, s, s);
  }
  ctx.globalAlpha = 1;

  // itens
  for (const p of J.poderes) desenharPoder(sx(p.x), sy(p.y), p, tempo);

  // partículas
  for (const p of J.part) {
    const a = clamp(p.vida / p.max, 0, 1);
    ctx.globalAlpha = a;
    ctx.fillStyle = p.tipo === "ouro" ? "#fbbf24" : p.tipo === "menta" ? "#5cd7b3" : "#4ddf84";
    const s = (p.tipo === "ouro" ? 6 : 3.5) * DPR;
    ctx.fillRect(sx(p.x) - s / 2, sy(p.y) - s / 2, s, s);
  }
  ctx.globalAlpha = 1;

  // laser + drone
  const dx = sx(d.x), dy = sy(d.y);
  const fix = J.decorrido < J.fixAte && !J.demo;
  if (J.estado === "voo" || J.demo || J.estado === "contagem") desenharLaser(dx, dy, d.ang, E.raio * (fix ? 1.8 : 1) * esc, tempo, fix, d.alt);
  for (const u of J.urubus) desenharUrubu(sx(u.x), sy(u.y), u);
  desenharDrone(dx, dy, d, tempo);

  // textos flutuantes
  ctx.textAlign = "center";
  for (const t of J.textos) {
    const a = clamp(t.vida / t.max * 1.6, 0, 1);
    ctx.globalAlpha = a;
    ctx.font = `900 ${Math.round(Math.min(W, H) * 0.032)}px "Segoe UI", system-ui, sans-serif`;
    ctx.lineWidth = 5 * DPR; ctx.strokeStyle = "rgba(3,7,18,.85)";
    ctx.strokeText(t.txt, sx(t.x), sy(t.y)); ctx.fillStyle = t.cor; ctx.fillText(t.txt, sx(t.x), sy(t.y));
  }
  ctx.globalAlpha = 1; ctx.textAlign = "start";
}

function desenharLaser(x, y, ang, r, tempo, fix, alt) {
  if (alt < 0.3) return;
  const cor = fix ? "92,215,179" : "255,59,107";
  const nx = -Math.sin(ang), ny = Math.cos(ang);        // perpendicular ao rumo
  const tras = r * 0.3, cx = x - Math.cos(ang) * tras, cy = y - Math.sin(ang) * tras;
  const ax = cx + nx * r, ay = cy + ny * r, bx = cx - nx * r, by = cy - ny * r;
  // leque do laser
  const g = ctx.createLinearGradient(x, y, cx, cy);
  g.addColorStop(0, `rgba(${cor},.05)`); g.addColorStop(1, `rgba(${cor},.28)`);
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(ax, ay); ctx.lineTo(bx, by); ctx.closePath(); ctx.fill();
  // faixa no chão
  ctx.lineCap = "round";
  ctx.strokeStyle = `rgba(${cor},.25)`; ctx.lineWidth = 12 * DPR;
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
  ctx.strokeStyle = `rgba(${cor},.95)`; ctx.lineWidth = 2.5 * DPR;
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
  // ponto de varredura indo e voltando
  const s = Math.sin(tempo * 16), px = cx + nx * r * s, py = cy + ny * r * s;
  ctx.fillStyle = "#fff";
  ctx.beginPath(); ctx.arc(px, py, 4 * DPR, 0, 7); ctx.fill();
  ctx.strokeStyle = `rgba(${cor},.7)`; ctx.lineWidth = 1.5 * DPR;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(px, py); ctx.stroke();
}

function desenharDrone(x, y, d, tempo) {
  const T = Math.min(W, H) * 0.06 * (0.75 + 0.25 * d.alt);
  const bob = Math.sin(tempo * 3.2) * T * 0.03 * d.alt;
  // sombra (afasta com a altura)
  ctx.save();
  ctx.translate(x + T * 0.5 * d.alt, y + T * 0.65 * d.alt);
  ctx.rotate(d.ang + Math.PI / 2);
  ctx.fillStyle = "rgba(0,0,0,.45)";
  ctx.beginPath(); ctx.ellipse(0, 0, T * 0.62, T * 0.62, 0, 0, 7); ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.translate(x, y + bob);
  ctx.rotate(d.ang + Math.PI / 2 + (d.tonto > 0 ? Math.sin(tempo * 30) * 0.4 : 0));
  // braços
  ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = T * 0.12; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(-T * 0.5, -T * 0.5); ctx.lineTo(T * 0.5, T * 0.5); ctx.moveTo(T * 0.5, -T * 0.5); ctx.lineTo(-T * 0.5, T * 0.5); ctx.stroke();
  // hélices
  for (const [hx, hy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
    const px = hx * T * 0.5, py = hy * T * 0.5;
    ctx.fillStyle = "rgba(226,232,240,.18)";
    ctx.beginPath(); ctx.arc(px, py, T * 0.34, 0, 7); ctx.fill();
    ctx.strokeStyle = "rgba(248,250,252,.75)"; ctx.lineWidth = T * 0.05;
    const a = tempo * 40 * (hx * hy) * (0.3 + d.alt);
    ctx.beginPath(); ctx.moveTo(px + Math.cos(a) * T * 0.32, py + Math.sin(a) * T * 0.32); ctx.lineTo(px - Math.cos(a) * T * 0.32, py - Math.sin(a) * T * 0.32); ctx.stroke();
    ctx.fillStyle = "#475569"; ctx.beginPath(); ctx.arc(px, py, T * 0.07, 0, 7); ctx.fill();
  }
  // corpo
  ctx.fillStyle = "#e2e8f0";
  ctx.beginPath(); ctx.roundRect ? ctx.roundRect(-T * 0.22, -T * 0.32, T * 0.44, T * 0.64, T * 0.12) : ctx.rect(-T * 0.22, -T * 0.32, T * 0.44, T * 0.64); ctx.fill();
  ctx.fillStyle = "#0f172a"; ctx.beginPath(); ctx.arc(0, -T * 0.2, T * 0.09, 0, 7); ctx.fill();   // câmera/sensor
  ctx.fillStyle = "#4ddf84"; ctx.beginPath(); ctx.arc(-T * 0.13, -T * 0.3, T * 0.04, 0, 7); ctx.arc(T * 0.13, -T * 0.3, T * 0.04, 0, 7); ctx.fill();
  ctx.fillStyle = Math.sin(tempo * 8) > 0 ? "#ff3b6b" : "#7f1d1d"; ctx.beginPath(); ctx.arc(0, T * 0.27, T * 0.045, 0, 7); ctx.fill();
  ctx.restore();
}

function desenharPoder(x, y, p, tempo) {
  const R = Math.min(W, H) * 0.028 * (1 + 0.08 * Math.sin(tempo * 6));
  const pisca = p.vida < 2.5 && Math.sin(tempo * 20) > 0;
  if (pisca) return;
  const cor = p.tipo === "bateria" ? "#4ddf84" : "#5cd7b3";
  ctx.fillStyle = "rgba(3,7,18,.75)"; ctx.strokeStyle = cor; ctx.lineWidth = 3 * DPR;
  ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill(); ctx.stroke();
  ctx.fillStyle = cor;
  if (p.tipo === "bateria") {
    ctx.fillRect(x - R * 0.42, y - R * 0.25, R * 0.75, R * 0.5);
    ctx.fillRect(x + R * 0.35, y - R * 0.12, R * 0.12, R * 0.24);
  } else {
    ctx.font = `900 ${Math.round(R * 0.62)}px "Segoe UI", sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("FIX", x, y + 1); ctx.textAlign = "start"; ctx.textBaseline = "alphabetic";
  }
}

function desenharUrubu(x, y, u) {
  const T = Math.min(W, H) * 0.035, asa = Math.sin(u.fase) * T * 0.35;
  ctx.save(); ctx.translate(x, y); ctx.scale(Math.sign(u.vx) || 1, 1);
  ctx.strokeStyle = "#0b0f19"; ctx.fillStyle = "#1f2937"; ctx.lineWidth = T * 0.16; ctx.lineCap = "round"; ctx.lineJoin = "round";
  ctx.beginPath(); ctx.moveTo(-T, -asa); ctx.quadraticCurveTo(-T * 0.4, -T * 0.25, 0, 0); ctx.quadraticCurveTo(T * 0.4, -T * 0.25, T, -asa); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(0, T * 0.05, T * 0.18, T * 0.12, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#f87171"; ctx.beginPath(); ctx.arc(T * 0.2, 0, T * 0.06, 0, 7); ctx.fill();
  ctx.restore();
}

/* ============================== HUD ============================== */
let hudCache = {};
function setTxt(id, v) { if (hudCache[id] !== v) { hudCache[id] = v; $(id).textContent = v; } }
function atualizarHUD() {
  const C = J.C, p = J.cadastrados / C.n;
  setTxt("#hud-imoveis", milhar(J.cadastrados));
  setTxt("#hud-pontos", milhar(J.pontos));
  setTxt("#hud-tempo", Math.ceil(J.tempo));
  setTxt("#hud-pct", `${Math.round(p * 100)}% da área de voo`);
  $("#hud-pct-barra").style.width = Math.min(100, p * 100) + "%";
  $("#hud-bateria-barra").style.width = clamp((J.tempo / cfg.duracao) * 100, 0, 100) + "%";
  $("#hud-bateria").classList.toggle("baixa", J.tempo <= 10);
  const combo = $("#hud-combo");
  combo.classList.toggle("on", J.combo > 1);
  setTxt("#hud-combo", `COMBO ×${J.combo}`);
  const e = C.x0 + J.drone.x, n = C.y0 + C.L - J.drone.y;
  setTxt("#hud-coord", `E ${milhar(e)}  N ${milhar(n)}  ·  SIRGAS 2000 / UTM 22S  ·  ${J.decorrido < J.fixAte ? "FIX" : "FLOAT"}`);
  if (performance.now() - (J.miniT || 0) > 200) { J.miniT = performance.now(); desenharMinimapa(); }
  if (J.msgAte && performance.now() > J.msgAte) { $("#hud-msg").classList.remove("on"); J.msgAte = 0; }
}
function desenharMinimapa() {
  const cv = $("#minimapa"), c = cv.getContext("2d"), S = cv.width, C = J.C;
  c.fillStyle = "#060c1a"; c.fillRect(0, 0, S, S);
  c.globalAlpha = 0.5; c.drawImage(cvRastro, 0, 0, S, S); c.globalAlpha = 1;
  c.drawImage(cvPredios, 0, 0, S, S);
  const k = S / C.L, v = J.E.vista;
  const a = W / Math.min(W, H), b = H / Math.min(W, H);
  c.strokeStyle = "rgba(248,250,252,.6)"; c.lineWidth = 1.5;
  c.strokeRect((J.cam.x - (v * a) / 2) * k, (J.cam.y - (v * b) / 2) * k, v * a * k, v * b * k);
  c.fillStyle = "#ff3b6b"; c.beginPath(); c.arc(J.drone.x * k, J.drone.y * k, 4, 0, 7); c.fill();
}
function mensagem(t1, t2, t3) {
  const m = $("#hud-msg");
  $(".m1", m).textContent = t1; $(".m2", m).textContent = t2; $(".m3", m).textContent = t3 || "";
  m.classList.add("on");
  J.msgAte = performance.now() + 2600;
}

/* ============================== IPTU: atual e potencial ============================== */
// IPTU arrecadado vem do Tesouro (Siconfi/DCA); a faixa de ganho vem de casos reais de recadastramento (dados/iptu.js)
function potencial(cod) {
  const v = IPTU[cod], m = MUN_POR_COD[cod];
  if (!v || !v.v) return null;
  if (CASOS && CASOS.min) return { tipo: "casos", ganhoMin: v.v * CASOS.min / 100, ganhoMax: v.v * CASOS.max / 100 };
  const gap = m ? (v.pcMed - v.pc) * m.pop : 0;
  return gap > 0 ? { tipo: "porte", ganhoMin: gap, ganhoMax: gap } : null;
}

/* ============================== telas ============================== */
function mostrarTela(id) {
  $$(".tela").forEach((t) => t.classList.toggle("ativa", t.id === id));
  $("#hud").classList.toggle("ativo", id === "hud");
  focarPrimeiro();
}
function focarPrimeiro() {
  $$(".btn.foco").forEach((b) => b.classList.remove("foco"));
  const tela = $(".tela.ativa");
  const b = tela && $(".btn-pri", tela);
  if (b) b.classList.add("foco");
}
function moverFoco(delta) {
  const tela = $(".tela.ativa") || ($("#pausa").classList.contains("ativo") ? $("#pausa") : null);
  if (!tela) return;
  const bs = $$(".btn", tela).filter((b) => b.offsetParent);
  if (!bs.length) return;
  let i = bs.findIndex((b) => b.classList.contains("foco"));
  bs.forEach((b) => b.classList.remove("foco"));
  i = (i + delta + bs.length) % bs.length;
  bs[i].classList.add("foco");
  Som.clique();
}
function clicarFoco() {
  const tela = $("#pausa").classList.contains("ativo") ? $("#pausa") : $(".tela.ativa");
  const b = tela && ($(".btn.foco", tela) || $(".btn-pri", tela));
  if (b) b.click();
}

async function irInicio() {
  Som.motorDesliga();
  $("#pausa").classList.remove("ativo");
  J.estado = "inicio";
  mostrarTela("tela-inicio");
  $("#premio-inicio").textContent = cfg.premio ? "🏆 Prêmio do dia: " + cfg.premio : "";
  $("#ranking-inicio").innerHTML = htmlRanking(null, 6);
  atualizarCTA(); atualizarAvisoSom();
  // voo de demonstração ao fundo
  const cod = ler(CHAVE.ultima, null) || "4204202";
  try { const C = await abrirCidade(cod); if (J.estado === "inicio") prepararPartida(C, true); } catch { /* sem mapa, sem demo */ }
}
function atualizarCTA() {
  const t = Ent.tipo === "pad" ? "Aperte A para começar" : document.body.classList.contains("toque") ? "Toque na tela para começar" : "Aperte Enter (ou A no controle) para começar";
  $("#cta-inicio").textContent = t;
}
function atualizarAvisoSom() { $("#som-aviso").classList.toggle("oculto", !cfg.som || Som.ativo()); }

/* ---------- escolha da cidade ---------- */
let filtro = [], focoCidade = 0;
function irCidade() {
  J.estado = "cidade";
  mostrarTela("tela-cidade");
  const b = $("#busca");
  b.value = "";
  filtrarCidades();
  setTimeout(() => b.focus(), 30);
}
function filtrarCidades() {
  const q = semAcento($("#busca").value.trim());
  filtro = q ? MUN.filter((m) => semAcento(m.n).includes(q)).sort((a, b) => semAcento(a.n).indexOf(q) - semAcento(b.n).indexOf(q) || a.n.localeCompare(b.n)) : [];
  if (!q) { const u = MUN_POR_COD[ler(CHAVE.ultima, "")]; filtro = u ? [u] : []; }
  filtro = filtro.slice(0, 7);
  focoCidade = 0;
  $("#lista-cidades").innerHTML = filtro.map((m, i) => `<li data-i="${i}" class="${i === focoCidade ? "foco" : ""}"><span>${esc(m.n)}</span><small>${milhar(m.edif)} edificações · ${milhar(m.pop)} hab.</small></li>`).join("")
    || (q ? `<li class="cinza">Nenhum município de SC com esse nome</li>` : "");
}
$("#busca").addEventListener("input", filtrarCidades);
$("#lista-cidades").addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) escolherCidade(filtro[+li.dataset.i]); });
function marcarFocoCidade() { $$("#lista-cidades li[data-i]").forEach((li, i) => li.classList.toggle("foco", i === focoCidade)); }

async function escolherCidade(m) {
  if (!m) return;
  Som.clique();
  gravar(CHAVE.ultima, m.c);
  $("#carregando").textContent = `Carregando ${m.n}…`;
  $("#carregando").classList.add("ativo");
  try {
    const C = await abrirCidade(m.c);
    $("#carregando").classList.remove("ativo");
    comecarVoo(C);
  } catch {
    $("#carregando").textContent = `O mapa de ${m.n} não foi encontrado na pasta "cidades".`;
    setTimeout(() => $("#carregando").classList.remove("ativo"), 2500);
  }
}

function comecarVoo(C) {
  $("#busca").blur();
  prepararPartida(C, false);
  J.estado = "contagem"; J.contagemT = 3.2;
  hudCache = {};
  $("#hud-cidade").textContent = C.nome;
  $("#hud-msg").classList.remove("on");
  const ajuda = { pad: "Analógico move o drone · segure A para turbo", toque: "Arraste o dedo para pilotar · TURBO acelera", teclado: "Setas ou WASD movem o drone · Espaço = turbo", mouse: "Clique e arraste para pilotar · Espaço = turbo" };
  $("#hud-ajuda").textContent = (ajuda[Ent.tipo] || ajuda.teclado) + " · pegue as casas douradas!";
  $("#hud-ajuda").classList.remove("some");
  $("#contagem").textContent = "3";
  mostrarTela("hud");
  atualizarHUD();
  Som.contagem(false);
}

function pausar(sim) {
  if (sim && J.estado === "voo") { J.estado = "pausa"; Som.motorDesliga(); $("#pausa").classList.add("ativo"); moverFocoPausa(); }
  else if (!sim && J.estado === "pausa") { J.estado = "voo"; $("#pausa").classList.remove("ativo"); Som.motorLiga(); ultimoT = performance.now(); }
}
function moverFocoPausa() { $$("#pausa .btn").forEach((b, i) => b.classList.toggle("foco", i === 0)); }

/* ---------- resultado ---------- */
function partidas() { return ler(CHAVE.partidas, []); }
function mostrarFim() {
  const C = J.C, p = J.cadastrados / C.n, m = MUN_POR_COD[C.c] || { n: C.nome, edif: C.edifMun };
  J.estado = "fim";
  const res = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), quando: new Date().toISOString(), dia: hoje(),
    municipioCod: C.c, municipio: C.nome, pontos: Math.round(J.pontos), imoveis: J.cadastrados, pct: Math.round(p * 1000) / 10,
    dourados: J.dourados, duracao: cfg.duracao,
  };
  const todas = partidas(); todas.push(res); gravar(CHAVE.partidas, todas);
  J.resultado = res; J.partidaId = res.id; J.fimEm = performance.now();
  const pos = posicaoHoje(res);
  $("#fim-titulo").textContent = p >= 0.5 ? "Cidade cadastrada!" : "Missão cumprida!";
  $("#fim-resumo").innerHTML = `Você cadastrou <b class="verde">${milhar(J.cadastrados)} imóveis</b> de <b>${esc(C.nome)}</b> em ${Math.round(J.decorrido)} segundos de voo.`;
  $("#fim-piada").textContent = "No jogo, eles já estão prontos para o CIB. Na vida real, a Autha faz isso com drone, laser e o sistema Autha-Geo.";
  $("#fim-placar").innerHTML = [
    [milhar(res.pontos), "pontos"],
    [pos ? `${pos}º` : "—", "lugar no ranking de hoje"],
    [`${res.pct.toLocaleString("pt-BR")}%`, "da área de voo cadastrada"],
    [milhar(J.dourados), J.dourados === 1 ? "área fora do cadastro achada" : "áreas fora do cadastro achadas"],
  ].map(([b, s]) => `<div><b>${b}</b><span>${s}</span></div>`).join("");
  $("#fim-iptu").innerHTML = htmlIptu(C.c, m);
  mostrarTela("tela-fim");
  atividade();
}

function htmlIptu(cod, m) {
  const v = IPTU[cod], pot = potencial(cod);
  const capital = cod === "4205407";
  const cib = capital ? "O CIB das capitais já está valendo." : "CIB obrigatório para imóveis urbanos a partir de janeiro de 2027.";
  const rs = (x) => x.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  let h = `<span class="chip">RAIO-X DO IPTU</span><h2>${esc(m.n)}</h2>`;
  h += `<div class="linha-iptu"><span>Edificações vistas por satélite</span><b>${milhar(m.edif)}</b></div>`;
  if (v && v.v) {
    h += `<div class="linha-iptu"><span>IPTU arrecadado em ${v.a}</span><b>${reais(v.v)}</b></div>`;
    h += `<div class="linha-iptu"><span>IPTU por habitante · mediana de SC (${esc(v.porte)})</span><b>${rs(v.pc)} · ${rs(v.pcMed)}</b></div>`;
  }
  if (pot && pot.tipo === "casos") {
    h += `<div class="ganho"><div class="valor">+${reais(pot.ganhoMin)} a ${reais(pot.ganhoMax)} por ano</div>
      <p>é o que o IPTU de ${esc(m.n)} subiria repetindo o resultado de municípios que fizeram recadastramento (+${CASOS.min}% a +${CASOS.max}%), <b>sem aumentar alíquota</b>.</p></div>`;
  } else if (pot) {
    h += `<div class="ganho"><div class="valor">+${reais(pot.ganhoMin)} por ano</div>
      <p>se ${esc(m.n)} arrecadasse por habitante o mesmo que a mediana dos municípios de SC do mesmo porte. Cadastro atualizado é o primeiro passo, e não depende de lei nova.</p></div>`;
  } else if (v && v.v) {
    h += `<div class="ganho"><p>${esc(m.n)} já arrecada acima da mediana do seu porte. O ganho agora é manter o cadastro vivo: ampliação que não entra no cadastro é IPTU que deixa de crescer.</p></div>`;
  }
  h += `<p class="nota">${cib} O relatório completo, com o método${CASOS ? " e os casos" : ""}, vai pelo WhatsApp.<br>
    Fontes: edificações — Overture Maps (out/2026); IPTU — Tesouro Nacional, Siconfi/DCA${v && v.a ? " " + v.a : ""}${CASOS ? "; casos — " + esc(CASOS.fonteCurta) : ""}. Estimativa para conversa, não é lançamento de imposto.</p>`;
  return h;
}

function posicaoHoje(res) {
  const lista = partidas().filter((p) => p.dia === res.dia && (p.nome || p.id === res.id));
  return lista.filter((p) => p.pontos > res.pontos).length + 1;
}

/* ---------- ficha ---------- */
function irFicha() {
  J.estado = "ficha";
  const r = J.resultado;
  $("#ficha-sub").innerHTML = `${esc(r.municipio)} · <b class="verde">${milhar(r.pontos)} pontos</b>. Seu nome e sua cidade aparecem no ranking da TV; o relatório <b>IPTU atual × potencial</b> chega no seu WhatsApp.`;
  ["#f-nome", "#f-whats", "#f-trib-nome", "#f-trib-whats", "#f-eng-nome", "#f-eng-whats"].forEach((s) => ($(s).value = ""));
  $("#f-consent").checked = false;
  $$("#f-cargo button").forEach((b) => b.classList.remove("marcado"));
  $$(".campo.erro, .consent.erro").forEach((e) => e.classList.remove("erro"));
  $("#ficha-erro").textContent = "";
  mostrarTela("tela-ficha");
  setTimeout(() => $("#f-nome").focus(), 30);
}
$("#f-cargo").innerHTML = CARGOS.map((c) => `<button type="button">${c}</button>`).join("");
$("#f-cargo").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const ja = b.classList.contains("marcado");
  $$("#f-cargo button").forEach((x) => x.classList.remove("marcado"));
  if (!ja) b.classList.add("marcado");
});
function mascaraTel(el) {
  el.addEventListener("input", () => {
    const d = digitos(el.value).slice(0, 11);
    el.value = d.length > 6 ? `(${d.slice(0, 2)}) ${d.slice(2, d.length - 4)}-${d.slice(-4)}` : d.length > 2 ? `(${d.slice(0, 2)}) ${d.slice(2)}` : d;
  });
}
["#f-whats", "#f-trib-whats", "#f-eng-whats"].forEach((s) => mascaraTel($(s)));
const telefoneOk = (s) => { const d = digitos(s); return d.length === 10 || d.length === 11; };

function salvarFicha() {
  const nome = $("#f-nome").value.trim().replace(/\s+/g, " ");
  const ok = { "#c-nome": nome.length >= 2, "#c-whats": telefoneOk($("#f-whats").value), "#c-consent": $("#f-consent").checked };
  Object.entries(ok).forEach(([s, v]) => $(s).classList.toggle("erro", !v));
  const falta = Object.entries(ok).filter(([, v]) => !v).map(([s]) => ({ "#c-nome": "o nome", "#c-whats": "o WhatsApp com DDD", "#c-consent": "a autorização" })[s]);
  if (falta.length) { $("#ficha-erro").textContent = "Falta preencher: " + falta.join(", ") + "."; return; }
  const todas = partidas(), r = todas.find((p) => p.id === J.partidaId);
  if (!r) return;
  Object.assign(r, {
    nome, cargo: ($("#f-cargo button.marcado") || {}).textContent || "", whatsapp: $("#f-whats").value.trim(),
    tributosNome: $("#f-trib-nome").value.trim(), tributosWhats: $("#f-trib-whats").value.trim(),
    engNome: $("#f-eng-nome").value.trim(), engWhats: $("#f-eng-whats").value.trim(), consentimento: true, fichaEm: new Date().toISOString(),
  });
  gravar(CHAVE.partidas, todas);
  J.resultado = r;
  irRankingFinal(r);
}

function irRankingFinal(r) {
  J.estado = "ranking";
  const pos = posicaoHoje(r);
  $("#final-titulo").textContent = pos === 1 ? `${r.nome.split(" ")[0]}, você está em 1º lugar!` : `${r.nome.split(" ")[0]}, você está em ${pos}º lugar!`;
  $("#final-texto").innerHTML = `O relatório <b>IPTU atual × potencial</b> de ${esc(r.municipio)} vai para o seu WhatsApp. ${cfg.premio ? "🏆 Prêmio do dia: " + esc(cfg.premio) + "." : ""}`;
  $("#ranking-final").innerHTML = htmlRanking(r.id, 10);
  mostrarTela("tela-ranking");
}

function htmlRanking(destaque, n) {
  const lista = partidas().filter((p) => p.dia === hoje() && p.nome).sort((a, b) => b.pontos - a.pontos);
  let top = lista.slice(0, n);
  const eu = destaque && lista.findIndex((p) => p.id === destaque);
  const linha = (p, i) => `<li class="${p.id === destaque ? "eu" : ""}"><span class="pos">${i + 1}º</span><span class="quem"><b>${esc(p.nome)}</b><small>${esc(p.municipio)}${p.cargo ? " · " + esc(p.cargo) : ""}</small></span><span class="pts">${milhar(p.pontos)}</span></li>`;
  let corpo = top.map(linha).join("");
  if (destaque && eu >= n) corpo += linha(lista[eu], eu);
  return `<h3>Ranking COMAC <small>hoje · ${new Date().toLocaleDateString("pt-BR")}</small></h3>` + (corpo ? `<ol>${corpo}</ol>` : `<div class="vazio">Ninguém voou ainda hoje. Seja o primeiro!</div>`);
}

/* ---------- ações (gamepad, teclado e clique caem aqui) ---------- */
function acao(nome) {
  atividade();
  if ($("#equipe").classList.contains("ativo")) return;
  const e = J.estado;
  if (e === "inicio") { if (["confirmar", "start"].includes(nome)) { Som.garantir(); irCidade(); } return; }
  if (e === "cidade") {
    if (nome === "cima") { focoCidade = Math.max(0, focoCidade - 1); marcarFocoCidade(); }
    else if (nome === "baixo") { focoCidade = Math.min(filtro.length - 1, focoCidade + 1); marcarFocoCidade(); }
    else if (nome === "confirmar" || nome === "start") escolherCidade(filtro[focoCidade]);
    else if (nome === "voltar") irInicio();
    return;
  }
  if (e === "voo") { if (nome === "start" || nome === "voltar") pausar(true); return; }
  if (e === "pausa") {
    if (nome === "confirmar" || nome === "start") clicarFoco();
    else if (nome === "voltar") sairDoVoo();
    else if (["cima", "baixo", "esquerda", "direita"].includes(nome)) {
      const bs = $$("#pausa .btn"), i = bs.findIndex((b) => b.classList.contains("foco"));
      bs.forEach((b) => b.classList.remove("foco")); bs[(i + 1) % bs.length].classList.add("foco");
    }
    return;
  }
  if (e === "fim") {
    if (performance.now() - J.fimEm < 1500) return;   // quem estava apertando o turbo não pula o resultado sem querer
    if (nome === "confirmar" || nome === "start") clicarFoco();
    else if (nome === "y") comecarVoo(J.C);
    else if (nome === "x" || nome === "voltar") irCidade();
    else if (nome === "esquerda" || nome === "cima") moverFoco(-1);
    else if (nome === "direita" || nome === "baixo") moverFoco(1);
    return;
  }
  if (e === "ficha") {
    if (nome === "confirmar") salvarFicha();
    else if (nome === "voltar") { J.estado = "fim"; mostrarTela("tela-fim"); }
    return;
  }
  if (e === "ranking") { if (["confirmar", "start", "voltar"].includes(nome)) irInicio(); }
}
function sairDoVoo() { $("#pausa").classList.remove("ativo"); J.estado = "inicio"; irInicio(); }

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-acao]");
  if (!b) return;
  Som.clique();
  const a = b.dataset.acao;
  ({
    continuar: () => pausar(false), sair: sairDoVoo, ficha: irFicha, "de-novo": () => comecarVoo(J.C), "outra-cidade": irCidade,
    "salvar-ficha": salvarFicha, "voltar-fim": () => { J.estado = "fim"; mostrarTela("tela-fim"); }, inicio: irInicio,
  })[a]?.();
});
$("#tela-inicio").addEventListener("click", () => { if (J.estado === "inicio") acao("confirmar"); });

function verificarInatividade() {
  const parado = (performance.now() - ultimaAtividade) / 1000;
  if (["fim", "ficha", "ranking", "cidade"].includes(J.estado) && parado > cfg.voltarInicio * (J.estado === "ficha" ? 3 : 1)) { atividade(); irInicio(); }
  if (J.estado === "pausa" && parado > cfg.voltarInicio * 2) { atividade(); sairDoVoo(); }
}

/* ============================== área da equipe ============================== */
$("#btn-equipe").addEventListener("click", abrirEquipe);
function abrirEquipe() {
  if (J.estado === "voo") pausar(true);
  const todas = partidas(), deHoje = todas.filter((p) => p.dia === hoje()), fichas = todas.filter((p) => p.nome);
  const conta = (l, f) => l.filter(f).length;
  const dur = [30, 45, 60, 90].map((s) => `<button class="btn ${cfg.duracao === s ? "marcado" : ""}" data-dur="${s}">${s} s</button>`).join("");
  const ult = fichas.slice(-40).reverse();
  $("#equipe-caixa").innerHTML = `
    <h2>Área da equipe</h2>
    <div class="numeros">
      <div><b>${deHoje.length}</b><span>voos hoje</span></div>
      <div><b>${conta(deHoje, (p) => p.nome)}</b><span>fichas hoje</span></div>
      <div><b>${conta(deHoje, (p) => p.cargo === "Prefeito(a)")}</b><span>prefeitos hoje</span></div>
      <div><b>${fichas.length}</b><span>fichas no total</span></div>
    </div>
    <h3>Duração do voo</h3><div class="linha">${dur}</div>
    <h3>Prêmio do dia (aparece na tela inicial e no ranking)</h3>
    <div class="linha"><input type="text" id="eq-premio" value="${esc(cfg.premio)}" placeholder="Ex.: voo de drone com Raio-X de até 30 ha"></div>
    <h3>Som</h3><div class="linha"><button class="btn ${cfg.som ? "marcado" : ""}" data-som="1">Ligado</button><button class="btn ${!cfg.som ? "marcado" : ""}" data-som="0">Desligado</button></div>
    <h3>Planilha e relatórios</h3>
    <div class="linha">
      <button class="btn btn-pri" data-eq="csv">Baixar planilha (todas as fichas e voos)</button>
      <button class="btn" data-eq="tela-cheia">Tela cheia</button>
      <button class="btn" data-eq="limpar">Apagar o ranking de hoje…</button>
      <button class="btn" data-eq="fechar">Fechar (Esc)</button>
    </div>
    <h3>Últimas fichas — clique em “Relatório” para abrir, imprimir em PDF e mandar no WhatsApp</h3>
    ${ult.length ? `<table><tr><th>Quando</th><th>Nome</th><th>Cargo</th><th>Município</th><th>WhatsApp</th><th>Pontos</th><th></th></tr>${ult.map((p) => `<tr><td>${new Date(p.quando).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</td><td>${esc(p.nome)}</td><td>${esc(p.cargo)}</td><td>${esc(p.municipio)}</td><td>${esc(p.whatsapp)}</td><td>${milhar(p.pontos)}</td><td><a href="relatorio.html?c=${p.municipioCod}&n=${encodeURIComponent(p.nome)}&cargo=${encodeURIComponent(p.cargo || "")}" target="_blank">Relatório</a></td></tr>`).join("")}</table>` : `<p class="cinza">Nenhuma ficha ainda.</p>`}`;
  $("#equipe").classList.add("ativo");
}
function fecharEquipe() {
  const pr = $("#eq-premio");
  if (pr) { cfg.premio = pr.value.trim(); gravar(CHAVE.config, cfg); }
  $("#equipe").classList.remove("ativo");
  if (J.estado === "inicio") irInicio();
}
$("#equipe").addEventListener("click", (e) => {
  if (e.target.id === "equipe") return fecharEquipe();
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.dur) { cfg.duracao = +b.dataset.dur; gravar(CHAVE.config, cfg); abrirEquipe(); }
  else if (b.dataset.som) { cfg.som = b.dataset.som === "1"; gravar(CHAVE.config, cfg); Som.garantir(); abrirEquipe(); atualizarAvisoSom(); }
  else if (b.dataset.eq === "csv") baixarCSV();
  else if (b.dataset.eq === "tela-cheia") { document.documentElement.requestFullscreen?.(); }
  else if (b.dataset.eq === "limpar") {
    if (confirm("Apagar o ranking de HOJE? As fichas continuam na planilha; só saem do ranking da TV.")) {
      gravar(CHAVE.partidas, partidas().map((p) => (p.dia === hoje() ? { ...p, dia: p.dia + "-arquivado" } : p)));
      abrirEquipe();
    }
  }
  else if (b.dataset.eq === "fechar") fecharEquipe();
});

function baixarCSV() {
  const cols = [["quando", "Data e hora"], ["municipio", "Município"], ["municipioCod", "Código IBGE"], ["nome", "Nome"], ["cargo", "Cargo"], ["whatsapp", "WhatsApp"],
    ["tributosNome", "Tributos - nome"], ["tributosWhats", "Tributos - WhatsApp"], ["engNome", "Engenheiro - nome"], ["engWhats", "Engenheiro - WhatsApp"],
    ["pontos", "Pontos"], ["imoveis", "Imóveis cadastrados"], ["pct", "% da área de voo"], ["dourados", "Áreas fora do cadastro"], ["duracao", "Duração (s)"], ["consentimento", "Autorizou contato"]];
  const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const linhas = [cols.map((c) => q(c[1])).join(";")].concat(partidas().map((p) => cols.map(([k]) => q(k === "quando" ? new Date(p[k]).toLocaleString("pt-BR") : k === "consentimento" ? (p[k] ? "sim" : "") : p[k])).join(";")));
  const blob = new Blob(["﻿" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `voo-cadastral_fichas_${hoje()}.csv`; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ============================== partida ============================== */
irInicio();
requestAnimationFrame(quadro);
