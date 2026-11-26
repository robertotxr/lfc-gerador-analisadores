'use strict';

/* ================================================================ utilidades */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const reduzMovimento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

async function chamar(rota, dados) {
  const r = await fetch('/api/' + rota, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.erro || 'erro desconhecido');
  return j;
}

function rolarDentro(caixa, el) {
  if (!caixa || !el) return;
  const c = caixa.getBoundingClientRect(), e = el.getBoundingClientRect();
  if (e.top < c.top + 30) caixa.scrollTop += e.top - c.top - 30;
  else if (e.bottom > c.bottom - 10) caixa.scrollTop += e.bottom - c.bottom + 40;
  if (e.left < c.left) caixa.scrollLeft += e.left - c.left - 20;
  else if (e.right > c.right) caixa.scrollLeft += e.right - c.right + 20;
}

/* ================================================================ editor com linhas */
const editores = {};

function criarEditor(id) {
  const caixa = document.getElementById(id);
  caixa.innerHTML = '<pre class="gutter" aria-hidden="true"></pre><textarea spellcheck="false" autocapitalize="off" autocomplete="off"></textarea>';
  const gutter = $('.gutter', caixa);
  const ta = $('textarea', caixa);
  ta.setAttribute('aria-label', caixa.closest('.bloco')?.querySelector('h2')?.textContent || id);
  let ruim = null;
  const numerar = () => {
    const n = ta.value.split('\n').length;
    let html = '';
    for (let i = 1; i <= n; i++) html += `<span${i === ruim ? ' class="ruim"' : ''}>${i}</span>`;
    gutter.innerHTML = html;
    gutter.scrollTop = ta.scrollTop;
  };
  ta.addEventListener('input', () => { ruim = null; numerar(); });
  ta.addEventListener('scroll', () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      const { selectionStart: a, selectionEnd: b } = ta;
      ta.setRangeText('  ', a, b, 'end');
      numerar();
    }
  });
  const ed = {
    get: () => ta.value,
    set: (v) => { ta.value = v; ruim = null; numerar(); ta.scrollTop = 0; },
    marcar: (linha) => { ruim = linha; numerar(); },
    foco: () => ta.focus(),
    ta,
  };
  editores[id] = ed;
  numerar();
  return ed;
}

function mostrarErro(idErro, editor, e) {
  const p = document.getElementById(idErro);
  if (!e) { p.hidden = true; editor && editor.marcar(null); return; }
  p.textContent = e.message || String(e);
  p.hidden = false;
  const m = /linha (\d+)/.exec(p.textContent);
  if (m && editor) editor.marcar(Number(m[1]));
}

/* ================================================================ rota de etapas */
const ROTAS = {
  lexico: [['definicoes', 'Definições'], ['padroes', 'AFD de cada padrão'], ['uniao', 'União por &'], ['tabela', 'Tabela léxica'], ['tokens', 'Tokens']],
  sintatico: [['gramatica', 'Gramática'], ['firstfollow', 'First e Follow'], ['colecao', 'Coleção LR(0)'], ['tabela', 'Tabela SLR'], ['pilha', 'Pilha']],
  compilar: [['codigo', 'Código'], ['tokens', 'Tokens'], ['ts', 'Tabela de símbolos'], ['pilha', 'Pilha']],
};

function desenharRota(aba, atual, prontas, acender = false) {
  const ol = document.getElementById('rota-' + aba);
  ol.innerHTML = ROTAS[aba].map(([id, rot], i) => {
    const ok = prontas.has(id);
    const cls = [ok ? 'feita' : '', id === atual ? 'atual' : '', acender && ok ? 'acendeu' : ''].join(' ');
    return `<li class="${cls}" style="--i:${i}"><button data-parada="${id}" ${ok ? '' : 'disabled'} ${id === atual ? 'aria-current="step"' : ''}>
      <span class="boia">${i + 1}</span><span>${esc(rot)}</span></button></li>`;
  }).join('');
  if (acender) $$('.acendeu .boia', ol).forEach((b, i) => { b.style.animationDelay = `${i * 110}ms`; });
  $$('button[data-parada]', ol).forEach((b) => b.addEventListener('click', () => irPara(aba, b.dataset.parada)));
}

/* ================================================================ desenho de autômatos */
function svgAutomato(af) {
  const N = af.estados.length;
  if (!N) return '<p class="vazio">Autômato sem estados.</p>';
  const R = 19;
  const suc = Array.from({ length: N }, () => []);
  const ant = Array.from({ length: N }, () => []);
  for (const e of af.arestas) if (e.de !== e.para) { suc[e.de].push(e.para); ant[e.para].push(e.de); }
  const ini = (af.estados.find((s) => s.inicial) || af.estados[0]).id;
  const nivel = new Array(N).fill(-1);
  nivel[ini] = 0;
  const fila = [ini];
  while (fila.length) {
    const q = fila.shift();
    for (const p of suc[q]) if (nivel[p] < 0) { nivel[p] = nivel[q] + 1; fila.push(p); }
  }
  const maxAlc = Math.max(...nivel);
  for (let q = 0; q < N; q++) if (nivel[q] < 0) nivel[q] = maxAlc + 1;
  const camadas = [];
  for (let q = 0; q < N; q++) (camadas[nivel[q]] = camadas[nivel[q]] || []).push(q);
  const ordem = {};
  camadas.forEach((c) => c.forEach((q, i) => { ordem[q] = i; }));
  for (let it = 0; it < 3; it++) {
    for (let l = 1; l < camadas.length; l++) {
      const bari = (q) => {
        const ps = ant[q].filter((p) => nivel[p] < l);
        return ps.length ? ps.reduce((s, p) => s + ordem[p], 0) / ps.length : ordem[q];
      };
      camadas[l].sort((a, b) => bari(a) - bari(b));
      camadas[l].forEach((q, i) => { ordem[q] = i; });
    }
  }
  const maxCam = Math.max(...camadas.map((c) => c.length));
  const DX = 165, DY = maxCam > 4 ? 112 : 132, TOPO = 86;
  const H = TOPO + (maxCam - 1) * DY + 56;
  const W = 70 + (camadas.length - 1) * DX + 110;
  const pos = {};
  camadas.forEach((c, l) => c.forEach((q, i) => {
    pos[q] = { x: 70 + l * DX, y: TOPO + ((maxCam - c.length) * DY) / 2 + i * DY };
  }));

  const pares = new Set(af.arestas.map((e) => e.de + '>' + e.para));
  const curto = (t) => (t.length > 20 ? t.slice(0, 19) + '…' : t);
  let arestas = '';
  for (const e of af.arestas) {
    const eps = e.rotulo.split(', ').includes('&');
    const titulo = `<title>q${e.de} → q${e.para}: ${esc(e.rotulo)}</title>`;
    const a = pos[e.de], b = pos[e.para];
    if (e.de === e.para) {
      const d = `M ${a.x - 9} ${a.y - R + 2} C ${a.x - 34} ${a.y - R - 46}, ${a.x + 34} ${a.y - R - 46}, ${a.x + 9} ${a.y - R + 2}`;
      arestas += `<g class="aresta${eps ? ' eps' : ''}">${titulo}<path d="${d}" marker-end="url(#seta)"/><text x="${a.x}" y="${a.y - R - 40}">${esc(curto(e.rotulo))}</text></g>`;
      continue;
    }
    const dl = nivel[e.para] - nivel[e.de];
    let curva = 0;
    if (pares.has(e.para + '>' + e.de)) curva = 26;
    if (dl === 0) curva = 42;
    if (dl < 0) curva = 46 + 10 * Math.min(4, -dl);
    if (dl > 1 && curva === 0) curva = 22;
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    const cx = (a.x + b.x) / 2 + nx * curva, cy = (a.y + b.y) / 2 + ny * curva;
    const un = (px, py, qx, qy) => { const l = Math.hypot(qx - px, qy - py) || 1; return [(qx - px) / l, (qy - py) / l]; };
    const [ux, uy] = un(a.x, a.y, cx, cy);
    const [vx, vy] = un(b.x, b.y, cx, cy);
    const sx = a.x + ux * R, sy = a.y + uy * R, ex = b.x + vx * (R + 1), ey = b.y + vy * (R + 1);
    const lx = 0.25 * sx + 0.5 * cx + 0.25 * ex, ly = 0.25 * sy + 0.5 * cy + 0.25 * ey;
    arestas += `<g class="aresta${eps ? ' eps' : ''}">${titulo}<path d="M ${sx} ${sy} Q ${cx} ${cy} ${ex} ${ey}" marker-end="url(#seta${eps ? '-eps' : ''})"/><text x="${lx}" y="${ly - 5}">${esc(curto(e.rotulo))}</text></g>`;
  }
  let nos = '';
  for (const s of af.estados) {
    const p = pos[s.id];
    const cls = ['no', s.token ? 'final' : '', s.inicial ? 'inicial' : ''].join(' ');
    const desc = s.descricao ? ` (${esc(s.descricao)})` : '';
    nos += `<g class="${cls}"><title>q${s.id}${desc}${s.token ? ', reconhece ' + esc(s.token) : ''}</title>`;
    if (s.inicial) nos += `<line class="entrada-seta" x1="${p.x - R - 34}" y1="${p.y}" x2="${p.x - R - 3}" y2="${p.y}" marker-end="url(#seta-ini)"/>`;
    nos += `<circle class="fora" cx="${p.x}" cy="${p.y}" r="${R}"/>`;
    if (s.token) nos += `<circle class="dentro" cx="${p.x}" cy="${p.y}" r="${R - 4}"/>`;
    nos += `<text x="${p.x}" y="${p.y}">q${s.id}</text>`;
    if (s.token) nos += `<text class="tok" x="${p.x}" y="${p.y + R + 13}">${esc(s.token)}</text>`;
    nos += '</g>';
  }
  const marcador = (id, cor) => `<marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${cor}"/></marker>`;
  return `<svg class="automato" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Diagrama do autômato com ${N} estados">
    <defs>${marcador('seta', '#5D6E83')}${marcador('seta-eps', '#1D5FAF')}${marcador('seta-ini', '#1D5FAF')}</defs>${arestas}${nos}</svg>`;
}

function tabelaAutomato(af, composicao = true) {
  const cols = af.colunas;
  let h = '<div class="envolve"><table class="tab"><thead><tr><th></th><th>δ</th>';
  h += cols.map((c) => `<th>${esc(c)}</th>`).join('') + '<th>Token</th>' + (composicao ? '<th>Composição</th>' : '') + '</tr></thead><tbody>';
  for (const s of af.estados) {
    const marca = (s.inicial ? '→' : '') + (s.token ? '*' : '');
    h += `<tr><td class="marca">${marca}</td><td>q${s.id}</td>`;
    s.destinos.forEach((d, i) => {
      if (!d.length) h += '<td class="vazia">–</td>';
      else if (af.deterministico && cols[i] !== '&') h += `<td>q${d[0]}</td>`;
      else h += `<td>{${d.map((x) => 'q' + x).join(',')}}</td>`;
    });
    h += `<td class="tk">${esc(s.token || '')}</td>` + (composicao ? `<td class="comp">${esc(s.descricao)}</td>` : '') + '</tr>';
  }
  return h + '</tbody></table></div>';
}

function blocoAutomato(titulo, af, extra = '') {
  const tipo = af.deterministico ? 'AFD' : 'AFND';
  return `<div><h4>${esc(titulo)}</h4>
    <p class="resumo-min">${tipo} com <b>${af.estados.length}</b> estados, <b>${af.estados.filter((s) => s.token).length}</b> finais e <b>${af.transicoes}</b> transições.</p>
    ${extra}<div class="diagrama">${svgAutomato(af)}</div>${tabelaAutomato(af)}</div>`;
}

/* ================================================================ código com tokens */
const cores = {};
function corDe(padrao) {
  if (!(padrao in cores)) cores[padrao] = 'c' + (Object.keys(cores).length % 8);
  return cores[padrao];
}

function codigoComTokens(texto, tokens, { atual = -1, parou = -1 } = {}) {
  const inicios = [0];
  for (let i = 0; i < texto.length; i++) if (texto[i] === '\n') inicios.push(i + 1);
  const marcas = tokens.map((t, i) => ({ i, t, a: inicios[t.linha - 1] + t.coluna - 1 })).sort((x, y) => x.a - y.a);
  let html = '', cur = 0;
  for (const { i, t, a } of marcas) {
    if (a < cur) continue;
    html += esc(texto.slice(cur, a));
    const pr = t.atributo === 'PR';
    const cls = ['t', t.erro ? 'ruim' : pr ? 'pr' : corDe(t.padrao), i === atual ? 'atual' : '', i === parou ? 'parou' : ''].join(' ');
    const dica = t.nome != null ? `<${t.lexema}, ${t.padrao}>   <${t.nome}, ${t.atributo}>` : `<${t.lexema}, ${t.padrao}>`;
    html += `<span class="${cls}" data-i="${i}" title="${esc(dica)}">${esc(t.lexema)}</span>`;
    cur = a + t.lexema.length;
  }
  html += esc(texto.slice(cur));
  const n = texto.split('\n').length;
  const nums = Array.from({ length: n }, (_, k) => k + 1).join('\n');
  return `<div class="codigo"><div class="nums">${nums}</div><pre>${html}</pre></div>`;
}

function legenda(tokens) {
  const ps = [...new Set(tokens.filter((t) => !t.erro && t.atributo !== 'PR').map((t) => t.padrao))];
  let h = ps.map((p) => `<span class="${corDe(p)}">${esc(p)}</span>`).join('');
  if (tokens.some((t) => t.atributo === 'PR')) h += '<span class="pr" style="font-weight:700;background:#EEF1F5">palavra reservada</span>';
  if (tokens.some((t) => t.erro)) h += '<span style="background:#FDE3E5;color:#D1343F">erro!</span>';
  return `<div class="legenda">${h}</div>`;
}

/* ================================================================ player da pilha */
const ICONES = {
  inicio: '<svg viewBox="0 0 16 16"><path d="M3 3h2v10H3zM13 3v10L6 8z"/></svg>',
  volta: '<svg viewBox="0 0 16 16"><path d="M11 3v10L4 8z"/></svg>',
  tocar: '<svg viewBox="0 0 16 16"><path d="M4 2.5v11L13 8z"/></svg>',
  pausar: '<svg viewBox="0 0 16 16"><path d="M4 3h3v10H4zM9 3h3v10H9z"/></svg>',
  avanca: '<svg viewBox="0 0 16 16"><path d="M5 3v10l7-5z"/></svg>',
  fim: '<svg viewBox="0 0 16 16"><path d="M11 3h2v10h-2zM3 3v10l7-5z"/></svg>',
};

function classeAcao(acao) {
  if (acao.startsWith('empilha')) return 'empilha';
  if (acao.startsWith('reduz')) return 'reduz';
  if (acao.startsWith('aceita')) return 'aceita';
  return 'erro';
}

function montarPlayer(el, analise, opcoes = {}) {
  const passos = analise.passos;
  let i = 0, timer = null, intervalo = 420;
  el.innerHTML = `<div class="player" tabindex="0" aria-label="Pilha de execução: use as setas para navegar">
    <div class="controles">
      <button data-a="inicio" title="Primeiro passo (Home)" aria-label="Primeiro passo">${ICONES.inicio}</button>
      <button data-a="volta" title="Passo anterior (seta esquerda)" aria-label="Passo anterior">${ICONES.volta}</button>
      <button data-a="tocar" class="tocar" title="Tocar / pausar (espaço)" aria-label="Tocar">${ICONES.tocar}</button>
      <button data-a="avanca" title="Próximo passo (seta direita)" aria-label="Próximo passo">${ICONES.avanca}</button>
      <button data-a="fim" title="Último passo (End)" aria-label="Último passo">${ICONES.fim}</button>
      <input type="range" min="0" max="${passos.length - 1}" value="0" aria-label="Passo">
      <select aria-label="Velocidade"><option value="700">devagar</option><option value="420" selected>normal</option><option value="120">rápido</option></select>
      <span class="passo-n"></span>
    </div>
    <div class="acao-atual"></div>
    <div><p class="faixa-rot">Pilha (estado embaixo, símbolo em cima; o topo é o último)</p><div class="faixa pilha"></div></div>
    <div><p class="faixa-rot">Entrada restante</p><div class="faixa fita"></div></div>
    ${opcoes.fonte != null ? '<div class="fonte-viva"></div>' : ''}
    <div class="passos-envolve"><table class="tab"><thead><tr><th>Passo</th><th>Pilha</th><th>Símbolos</th><th>Entrada</th><th>Ação</th></tr></thead><tbody></tbody></table></div>
  </div>`;
  const player = $('.player', el);
  const range = $('input[type=range]', el);
  const corpo = $('tbody', el);
  const fita = (pos) => analise.entrada.slice(pos).map((e) => e.terminal || e.texto).concat(['$']);

  let linhas = '';
  passos.forEach((p, k) => {
    const resto = fita(p.pos);
    const ent = resto.length > 8 ? resto.slice(0, 8).join(' ') + ' …' : resto.join(' ');
    const pil = p.pilha.length > 12 ? '… ' + p.pilha.slice(-12).join(' ') : p.pilha.join(' ');
    const sim = p.simbolos.length > 8 ? '… ' + p.simbolos.slice(-8).join(' ') : p.simbolos.join(' ');
    linhas += `<tr data-k="${k}"><td>${k + 1}</td><td>${esc(pil)}</td><td>${esc(sim)}</td><td>${esc(ent)}</td><td>${esc(p.acao)}</td></tr>`;
  });
  corpo.innerHTML = linhas;

  const mostrar = (k) => {
    i = Math.max(0, Math.min(passos.length - 1, k));
    const p = passos[i];
    range.value = i;
    $('.passo-n', el).textContent = `passo ${i + 1} de ${passos.length}`;
    const ac = $('.acao-atual', el);
    ac.className = 'acao-atual ' + classeAcao(p.acao);
    const fim = i === passos.length - 1;
    ac.innerHTML = `<span class="rot">Ação</span>${esc(p.acao)}${fim && !analise.aceito ? `<div style="font-family:var(--ui);font-size:13px;margin-top:4px">${esc(analise.mensagem)}</div>` : ''}`;
    const MAX = 12;
    let cel = [];
    p.pilha.forEach((est, j) => cel.push({ est, sim: j === 0 ? '' : p.simbolos[j - 1] }));
    let pre = '';
    if (cel.length > MAX) { pre = `<div class="celula reticencias"><span class="sim">…</span><span class="est">+${cel.length - MAX}</span></div>`; cel = cel.slice(-MAX); }
    const faixaPilha = $('.pilha', el);
    faixaPilha.innerHTML = pre + cel.map((c, j) => `<div class="celula${j === cel.length - 1 ? ' topo-pilha' : ''}"><span class="sim">${esc(c.sim)}</span><span class="est">${c.est}</span></div>`).join('');
    faixaPilha.scrollLeft = faixaPilha.scrollWidth;
    const resto = fita(p.pos);
    const vis = resto.slice(0, 14);
    $('.fita', el).innerHTML = vis.map((t, j) => `<div class="celula${j === 0 ? ' cabeca' : ''}"><span class="est">${esc(t)}</span></div>`).join('') + (resto.length > 14 ? `<div class="celula reticencias"><span class="est">+${resto.length - 14}</span></div>` : '');
    $$('tr.atual', corpo).forEach((tr) => tr.classList.remove('atual'));
    const tr = corpo.children[i];
    if (tr) { tr.classList.add('atual'); rolarDentro($('.passos-envolve', el), tr); }
    if (opcoes.fonte != null) {
      const parou = fim && !analise.aceito;
      $('.fonte-viva', el).innerHTML = codigoComTokens(opcoes.fonte, opcoes.tokens, parou ? { parou: p.pos } : { atual: p.pos });
      const caixa = $('.fonte-viva .codigo', el);
      rolarDentro(caixa, $('.t.atual, .t.parou', caixa));
    }
  };
  const parar = () => { clearInterval(timer); timer = null; const b = $('[data-a=tocar]', el); b.innerHTML = ICONES.tocar; b.setAttribute('aria-label', 'Tocar'); };
  const tocar = () => {
    if (timer) return parar();
    if (i >= passos.length - 1) mostrar(0);
    const b = $('[data-a=tocar]', el); b.innerHTML = ICONES.pausar; b.setAttribute('aria-label', 'Pausar');
    timer = setInterval(() => { if (i >= passos.length - 1) parar(); else mostrar(i + 1); }, intervalo);
  };
  const acoes = { inicio: () => mostrar(0), volta: () => mostrar(i - 1), avanca: () => mostrar(i + 1), fim: () => mostrar(passos.length - 1), tocar };
  $$('.controles button', el).forEach((b) => b.addEventListener('click', () => { if (b.dataset.a !== 'tocar') parar(); acoes[b.dataset.a](); }));
  range.addEventListener('input', () => { parar(); mostrar(Number(range.value)); });
  $('.controles select', el).addEventListener('change', (e) => { intervalo = Number(e.target.value); if (timer) { parar(); tocar(); } });
  corpo.addEventListener('click', (e) => { const tr = e.target.closest('tr'); if (tr) { parar(); mostrar(Number(tr.dataset.k)); } });
  player.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
    const mapa = { ArrowRight: 'avanca', ArrowLeft: 'volta', Home: 'inicio', End: 'fim', ' ': 'tocar' };
    if (mapa[e.key]) { e.preventDefault(); if (e.key !== ' ') parar(); acoes[mapa[e.key]](); }
  });
  mostrar(opcoes.inicio === 'fim' ? passos.length - 1 : 0);
  el._parar = parar;
}

/* ================================================================ estado e navegação */
const estado = {
  aba: 'lexico',
  exemplos: null,
  lexico: { projeto: null, execucao: null, fonteUsada: '', parada: 'tabela', padrao: 0 },
  sintatico: { projeto: null, analise: null, parada: 'tabela', filtro: '' },
  compilar: { res: null, fonteUsada: '', parada: 'codigo' },
};

function prontas(aba) {
  const e = estado[aba], s = new Set();
  if (aba === 'lexico') {
    if (e.projeto) ['definicoes', 'padroes', 'uniao', 'tabela'].forEach((x) => s.add(x));
    if (e.execucao) s.add('tokens');
  } else if (aba === 'sintatico') {
    if (e.projeto) ['gramatica', 'firstfollow', 'colecao', 'tabela'].forEach((x) => s.add(x));
    if (e.analise) s.add('pilha');
  } else if (e.res) ['codigo', 'tokens', 'ts', 'pilha'].forEach((x) => s.add(x));
  return s;
}

function irPara(aba, parada, acender = false) {
  const folha = document.getElementById('folha-' + aba);
  if (folha._player && folha._player._parar) folha._player._parar();
  folha._player = null;
  folha.onclick = null;
  estado[aba].parada = parada;
  desenharRota(aba, parada, prontas(aba), acender);
  const vistas = { lexico: vistaLexico, sintatico: vistaSintatico, compilar: vistaCompilar };
  vistas[aba](folha, parada);
  folha.scrollTop = 0;
}

function trocarAba(aba) {
  estado.aba = aba;
  $$('.abas button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.aba === aba)));
  $$('.aba').forEach((s) => { s.hidden = s.id !== 'aba-' + aba; });
  preencherSeletor();
  history.replaceState(null, '', '#' + aba);
}

/* ================================================================ vistas: léxico */
function vistaLexico(folha, parada) {
  const { projeto: p, execucao: x } = estado.lexico;
  if (!p) { folha.innerHTML = '<p class="vazio">Escreva as definições regulares e clique em <b>Gerar analisador</b> para ver os autômatos de cada etapa.</p>'; return; }
  const avisos = p.avisos.length ? `<ul class="avisos">${p.avisos.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>` : '';
  if (parada === 'definicoes') {
    folha.innerHTML = `<section><h3>Definições regulares</h3>
      <p class="sub">Cada padrão de token vira um AFD. Definições referenciadas com {nome} são auxiliares e não geram token. Quando um lexema casa com mais de um padrão, vence o de menor número.</p>${avisos}
      <table class="tab texto"><thead><tr><th>Nome</th><th>Expressão regular</th><th>Papel</th></tr></thead><tbody>
      ${p.definicoes.map((d) => `<tr><td><b>${esc(d.nome)}</b></td><td style="font-family:var(--mono)">${esc(d.er)}</td><td>${d.auxiliar ? 'auxiliar' : 'token, prioridade ' + d.prioridade}</td></tr>`).join('')}
      </tbody></table></section>`;
  } else if (parada === 'padroes') {
    const k = Math.min(estado.lexico.padrao, p.padroes.length - 1);
    const pd = p.padroes[k];
    const mn = pd.minimizacao;
    const lista = (l) => (l.length ? l.map((q) => 'q' + q).join(', ') : 'nenhum');
    folha.innerHTML = `<section><h3>ER para AFD, padrão a padrão</h3>
      <p class="sub">Conversão direta do livro do Aho: a ER é aumentada com # no fim, cada folha recebe uma posição e o AFD é construído a partir de followpos. Depois o AFD é minimizado.</p>
      <div class="pilulas" role="group" aria-label="Padrão">${p.padroes.map((x, j) => `<button aria-pressed="${j === k}" data-k="${j}">${esc(x.nome)}</button>`).join('')}</div>
      <div class="er-exp">(${esc(pd.er_expandida)})#</div>
      <div class="lado-a-lado">
        <div><h4>Posições e followpos</h4>
          <p class="resumo-min">firstpos(raiz) = {${pd.firstpos.join(', ')}}, posição de # = ${pd.pos_fim}</p>
          <table class="tab"><thead><tr><th>Posição</th><th>Símbolo</th><th>followpos</th></tr></thead><tbody>
          ${pd.followpos.map((f) => `<tr><td>${f.pos}</td><td>${esc(f.simbolo)}</td><td>${f.simbolo === '#' ? '–' : '{' + f.follow.join(', ') + '}'}</td></tr>`).join('')}
          </tbody></table></div>
        ${blocoAutomato('AFD da conversão direta', pd.afd)}
      </div></section>
      <section>${blocoAutomato('AFD mínimo', mn.afd, `<p class="resumo-min">Inalcançáveis eliminados: <b>${lista(mn.inalcancaveis)}</b>. Mortos eliminados: <b>${lista(mn.mortos)}</b>. Classes de equivalência: ${mn.classes.map((c, j) => `q${j} = {${c.map((q) => 'q' + q).join(', ')}}`).join('; ')}.</p>`)}</section>`;
    $$('.pilulas button', folha).forEach((b) => b.addEventListener('click', () => { estado.lexico.padrao = Number(b.dataset.k); vistaLexico(folha, 'padroes'); }));
  } else if (parada === 'uniao') {
    folha.innerHTML = `<section><h3>União por &amp;-transições</h3>
      <p class="sub">Um novo estado inicial q0 com &amp;-transição para o inicial de cada AFD mínimo. Cada estado final guarda o padrão que reconhece. As colunas são classes de caracteres comuns a todos os AFDs.</p>
      ${blocoAutomato('AFND da união', p.uniao)}</section>`;
  } else if (parada === 'tabela') {
    const conf = p.conflitos.length ? `<ul class="avisos">${p.conflitos.map((c) => `<li>q${c.estado} é final de ${esc(c.padroes.join(' e '))}: vence ${esc(c.escolhido)} (definido primeiro)</li>`).join('')}</ul>` : '';
    const minExtra = p.minimizacao_final ? `<section>${blocoAutomato('Tabela léxica minimizada', p.minimizacao_final.afd)}</section>` : '';
    folha.innerHTML = `<section><h3>Tabela de análise léxica</h3>
      <p class="sub">O AFND da união determinizado pela construção de subconjuntos. A composição mostra os estados do AFND que formam cada estado. É esta tabela que a análise do texto fonte usa.</p>
      ${avisos}${conf}${blocoAutomato('AFD determinizado', p.determinizado)}</section>${minExtra}`;
  } else if (parada === 'tokens') {
    if (!x) { folha.innerHTML = '<p class="vazio">Escreva um texto fonte e clique em <b>Analisar texto</b>.</p>'; return; }
    const lista = x.tokens.map((t) => `<div class="${t.erro ? 'ruim' : ''}">${esc(`<${t.lexema}, ${t.padrao}>`)}</div>`).join('');
    folha.innerHTML = `<section><h3>Tokens</h3>
      <div class="barra"><span class="contagem"><b>${x.tokens.length}</b> tokens, <b>${x.erros}</b> ${x.erros === 1 ? 'erro léxico' : 'erros léxicos'}</span>
      <button class="secundario" id="copiar-tokens">Copiar lista</button></div>
      ${legenda(x.tokens)}${codigoComTokens(estado.lexico.fonteUsada, x.tokens)}</section>
      <section><h4>Lista de tokens (saída do analisador)</h4><div class="lista-tokens">${lista}</div></section>`;
    $('#copiar-tokens', folha).addEventListener('click', async (ev) => {
      await navigator.clipboard.writeText(x.tokens.map((t) => `<${t.lexema}, ${t.padrao}>`).join('\n') + '\n');
      ev.target.textContent = 'Copiada';
      setTimeout(() => { ev.target.textContent = 'Copiar lista'; }, 1400);
    });
  }
}

async function lexicoGerar(acender = true) {
  const btn = $('#lex-gerar');
  btn.disabled = true;
  try {
    estado.lexico.projeto = await chamar('lexico/projetar', { definicoes: editores['ed-lex-def'].get(), minimizar: $('#lex-min').checked });
    estado.lexico.padrao = 0;
    mostrarErro('erro-lex-def', editores['ed-lex-def'], null);
    irPara('lexico', estado.lexico.parada === 'tokens' ? 'tabela' : estado.lexico.parada, acender);
  } catch (e) {
    mostrarErro('erro-lex-def', editores['ed-lex-def'], e);
    estado.lexico.projeto = null; estado.lexico.execucao = null;
    irPara('lexico', 'definicoes');
    $('#folha-lexico').innerHTML = '<p class="vazio">As definições têm um erro, marcado ao lado. Corrija e clique em <b>Gerar analisador</b> de novo.</p>';
  } finally { btn.disabled = false; }
}

async function lexicoAnalisar() {
  const btn = $('#lex-analisar');
  btn.disabled = true;
  try {
    const fonte = editores['ed-lex-fonte'].get();
    const modo = $('#lex-modo [aria-checked=true]').dataset.modo;
    estado.lexico.execucao = await chamar('lexico/executar', { definicoes: editores['ed-lex-def'].get(), fonte, modo });
    estado.lexico.fonteUsada = fonte;
    mostrarErro('erro-lex-fonte', null, null);
    if (!estado.lexico.projeto) await lexicoGerar(false);
    irPara('lexico', 'tokens');
  } catch (e) {
    mostrarErro('erro-lex-def', editores['ed-lex-def'], e);
  } finally { btn.disabled = false; }
}

/* ================================================================ vistas: sintático */
function vistaSintatico(folha, parada) {
  const { projeto: p, analise: a } = estado.sintatico;
  if (!p) { folha.innerHTML = '<p class="vazio">Escreva a gramática e clique em <b>Gerar tabela SLR</b>.</p>'; return; }
  const avisos = p.avisos.length ? `<ul class="avisos">${p.avisos.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
  const conflitos = p.conflitos.length ? `<ul class="avisos">${p.conflitos.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
  if (parada === 'gramatica') {
    folha.innerHTML = `<section><h3>Gramática aumentada</h3>
      <p class="sub">A produção 0 é a inicial aumentada. Os números são os usados nas reduções da tabela (r3 = reduz pela produção 3).</p>${avisos}
      <table class="tab texto"><thead><tr><th>#</th><th>Produção</th></tr></thead><tbody>
      ${p.producoes.map((x) => `<tr><td>${x.n}</td><td style="font-family:var(--mono)">${esc(x.texto)}</td></tr>`).join('')}
      </tbody></table></section>
      <section><h4>Terminais</h4><div class="legenda">${p.terminais.map((t) => `<span class="c5">${esc(t)}</span>`).join('')}</div>
      ${p.palavras_reservadas.length ? `<h4>Palavras reservadas (vão para a tabela de símbolos antes da análise)</h4><div class="legenda">${p.palavras_reservadas.map((t) => `<span class="c0">${esc(t)}</span>`).join('')}</div>` : ''}</section>`;
  } else if (parada === 'firstfollow') {
    const conj = (l) => '{ ' + l.map(esc).join(', ') + ' }';
    folha.innerHTML = `<section><h3>First e Follow</h3>
      <p class="sub">& em First indica que o não terminal deriva a palavra vazia. $ é o fim da entrada.</p>
      <table class="tab"><thead><tr><th>Não terminal</th><th>First</th><th>Follow</th></tr></thead><tbody>
      ${p.nao_terminais.map((n) => `<tr><td><b>&lt;${esc(n)}&gt;</b></td><td>${conj(p.first[n])}</td><td>${conj(p.follow[n])}</td></tr>`).join('')}
      </tbody></table></section>`;
  } else if (parada === 'colecao') {
    folha.innerHTML = `<section><h3>Coleção canônica LR(0)</h3>
      <p class="sub">${p.estados.length} conjuntos de itens. Cada um é o fecho (closure) do seu núcleo; clique numa transição para ir ao estado de destino.</p>
      <input class="filtro" type="search" placeholder="Filtrar por item ou símbolo" value="${esc(estado.sintatico.filtro)}" aria-label="Filtrar estados">
      <div class="colecao">${p.estados.map((s) => `<div class="item-set" id="I${s.n}" data-busca="${esc(s.itens.join(' ').toLowerCase())}">
        <h4>I${s.n}</h4><ul>${s.itens.map((it) => `<li class="${/•$/.test(it) ? 'completo' : ''}" title="${esc(it)}">${esc(it)}</li>`).join('')}</ul>
        <div class="gotos">${s.goto.map((g) => `<button data-ir="${g.destino}" title="GOTO(I${s.n}, ${esc(g.simbolo)}) = I${g.destino}">${esc(g.simbolo)} ⇒ I${g.destino}</button>`).join('')}</div></div>`).join('')}</div></section>`;
    const filtro = $('.filtro', folha);
    const aplicar = () => {
      const t = filtro.value.toLowerCase().trim();
      estado.sintatico.filtro = filtro.value;
      $$('.item-set', folha).forEach((c) => { c.hidden = t && !c.dataset.busca.includes(t) && ('i' + c.id.slice(1)) !== t; });
    };
    filtro.addEventListener('input', aplicar);
    aplicar();
    folha.onclick = (e) => {
      const b = e.target.closest('[data-ir]');
      if (!b) return;
      filtro.value = ''; aplicar();
      const alvo = document.getElementById('I' + b.dataset.ir);
      alvo.scrollIntoView({ behavior: reduzMovimento ? 'auto' : 'smooth', block: 'center' });
      alvo.classList.remove('piscar'); void alvo.offsetWidth; alvo.classList.add('piscar');
    };
  } else if (parada === 'tabela') {
    const T = p.tabela;
    let h = '<div class="slr-envolve"><table class="tab"><thead><tr><th>Estado</th>';
    h += T.terminais.map((t) => `<th>${esc(t)}</th>`).join('');
    h += T.nao_terminais.map((n, j) => `<th class="${j === 0 ? 'desvio-ini' : ''}">&lt;${esc(n)}&gt;</th>`).join('') + '</tr></thead><tbody>';
    for (const l of T.linhas) {
      h += `<tr><td>${l.estado}</td>`;
      for (const t of T.terminais) {
        const v = l.acao[t] || '';
        const cls = [v.startsWith('s') ? 's' : v.startsWith('r') ? 'r' : v === 'acc' ? 'acc' : '', l.conflitos.includes(t) ? 'conflito' : ''].join(' ');
        h += `<td class="${cls}"${l.conflitos.includes(t) ? ' title="Conflito nesta célula"' : ''}>${esc(v)}</td>`;
      }
      T.nao_terminais.forEach((n, j) => { h += `<td class="desvio${j === 0 ? ' desvio-ini' : ''}">${l.desvio[n] ?? ''}</td>`; });
      h += '</tr>';
    }
    h += '</tbody></table></div>';
    const veredito = p.eh_slr
      ? '<p class="sub">A gramática é <b>SLR(1)</b>: nenhuma célula com duas ações.</p>'
      : `<p class="sub">A gramática <b>não é SLR(1)</b>. As células em vermelho tinham duas ações; a tabela segue resolvendo por empilhar antes de reduzir.</p>${conflitos}`;
    folha.innerHTML = `<section><h3>Tabela SLR</h3>
      <p class="sub">ACTION à esquerda (s = empilha e vai ao estado, r = reduz pela produção, acc = aceita) e GOTO à direita.</p>${veredito}${h}</section>`;
  } else if (parada === 'pilha') {
    if (!a) { folha.innerHTML = '<p class="vazio">Coloque uma lista de tokens e clique em <b>Analisar tokens</b>.</p>'; return; }
    folha.innerHTML = `<section><h3>Pilha de execução</h3>
      <p class="sub" style="color:${a.aceito ? 'var(--alga)' : 'var(--boia)'}"><b>${esc(a.mensagem)}</b></p><div class="player-alvo"></div></section>`;
    const alvo = $('.player-alvo', folha);
    montarPlayer(alvo, a);
    folha._player = alvo;
  }
}

async function sintaticoGerar(acender = true) {
  const btn = $('#sin-gerar');
  btn.disabled = true;
  try {
    estado.sintatico.projeto = await chamar('sintatico/projetar', { gramatica: editores['ed-sin-gram'].get(), palavras_reservadas: editores['ed-sin-pr'].get() });
    estado.sintatico.analise = null;
    mostrarErro('erro-sin-gram', editores['ed-sin-gram'], null);
    irPara('sintatico', estado.sintatico.parada === 'pilha' ? 'tabela' : estado.sintatico.parada, acender);
  } catch (e) {
    mostrarErro('erro-sin-gram', editores['ed-sin-gram'], e);
    estado.sintatico.projeto = null; estado.sintatico.analise = null;
    irPara('sintatico', 'gramatica');
    $('#folha-sintatico').innerHTML = '<p class="vazio">A gramática tem um erro, marcado ao lado. Corrija e clique em <b>Gerar tabela SLR</b> de novo.</p>';
  } finally { btn.disabled = false; }
}

async function sintaticoAnalisar() {
  const btn = $('#sin-analisar');
  btn.disabled = true;
  try {
    if (!estado.sintatico.projeto) await sintaticoGerar(false);
    estado.sintatico.analise = await chamar('sintatico/executar', {
      gramatica: editores['ed-sin-gram'].get(), palavras_reservadas: editores['ed-sin-pr'].get(), tokens: editores['ed-sin-tokens'].get(),
    });
    mostrarErro('erro-sin-tokens', editores['ed-sin-tokens'], null);
    irPara('sintatico', 'pilha');
  } catch (e) {
    mostrarErro('erro-sin-tokens', editores['ed-sin-tokens'], e);
  } finally { btn.disabled = false; }
}

/* ================================================================ vistas: compilar */
function vistaCompilar(folha, parada) {
  const r = estado.compilar.res;
  if (!r) { folha.innerHTML = '<p class="vazio">Escreva um programa e clique em <b>Compilar</b>.</p>'; return; }
  const fonte = estado.compilar.fonteUsada;
  const a = r.analise;
  const ultimo = a.passos[a.passos.length - 1];
  const idxErro = a.aceito ? -1 : ultimo.pos;
  if (parada === 'codigo') {
    const tokErro = r.tokens[idxErro];
    const avisos = [...r.avisos, ...r.lexico.avisos, ...r.sintatico.avisos, ...r.sintatico.conflitos];
    folha.innerHTML = `<section><h3>Código analisado</h3>
      <p class="sub">Cada token está colorido pelo seu padrão; passe o mouse para ver o token gerado.${idxErro >= 0 && tokErro ? ' O token onde a análise parou está marcado em vermelho.' : ''}</p>
      ${avisos.length ? `<ul class="avisos">${avisos.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${legenda(r.tokens)}${codigoComTokens(fonte, r.tokens, { parou: idxErro })}</section>`;
  } else if (parada === 'tokens') {
    folha.innerHTML = `<section><h3>Tokens</h3>
      <p class="sub">A mesma lista nos dois formatos: o do Trabalho I e o que vai para o sintático, já com a tabela de símbolos.</p>
      <div class="envolve"><table class="tab"><thead><tr><th>#</th><th>Linha:coluna</th><th>&lt;lexema, padrão&gt;</th><th>&lt;token, atributo&gt;</th></tr></thead><tbody>
      ${r.tokens.map((t, k) => `<tr${k === idxErro ? ' class="destacado"' : ''}><td>${k + 1}</td><td>${t.linha}:${t.coluna}</td><td>${esc(`<${t.lexema}, ${t.padrao}>`)}</td><td>${esc(`<${t.nome}, ${t.atributo}>`)}</td></tr>`).join('')}
      </tbody></table></div></section>`;
  } else if (parada === 'ts') {
    folha.innerHTML = `<section><h3>Tabela de símbolos</h3>
      <p class="sub">As palavras reservadas entram antes da análise; identificadores e constantes são inseridos na primeira vez que aparecem, e o token leva a linha da tabela.</p>
      <table class="tab"><thead><tr><th>Linha</th><th>Lexema</th><th>Categoria</th></tr></thead><tbody>
      ${r.ts.map((x) => `<tr><td>${x.linha}</td><td>${esc(x.lexema)}</td><td class="${x.categoria === 'PR' ? 'tk' : ''}">${esc(x.categoria)}</td></tr>`).join('')}
      </tbody></table></section>`;
  } else if (parada === 'pilha') {
    folha.innerHTML = `<section><h3>Pilha de execução</h3>
      <p class="sub">O token sendo lido aparece destacado no código. Use as setas do teclado ou o botão de tocar.</p><div class="player-alvo"></div></section>`;
    const alvo = $('.player-alvo', folha);
    montarPlayer(alvo, a, { fonte, tokens: r.tokens, inicio: a.aceito ? 'inicio' : 'fim' });
    folha._player = alvo;
  }
}

function desenharVeredito() {
  const r = estado.compilar.res, v = $('#veredito');
  if (!r) { v.hidden = true; return; }
  v.hidden = false;
  v.className = 'veredito ' + (r.ok ? 'ok' : 'falha');
  const msg = r.ok ? r.analise.mensagem
    : r.erros_lexicos && r.analise.aceito ? `${r.erros_lexicos} erro(s) léxico(s) no código.` : r.analise.mensagem;
  v.innerHTML = `<strong>${r.ok ? 'Código correto' : 'Código com erro'}</strong><span class="msg">${esc(msg)}</span>
    <span class="stats">${r.tokens.length} tokens, ${r.analise.passos.length} passos, tabela SLR com ${r.sintatico.estados} estados</span>`;
}

async function compilar(acender = true) {
  const btn = $('#comp-compilar');
  btn.disabled = true;
  try {
    const fonte = editores['ed-comp-fonte'].get();
    estado.compilar.res = await chamar('compilar', {
      lexico: editores['ed-comp-lexico'].get(), gramatica: editores['ed-comp-gramatica'].get(),
      palavras_reservadas: editores['ed-comp-pr'].get(), fonte,
    });
    estado.compilar.fonteUsada = fonte;
    $('#erro-comp').hidden = true;
    desenharVeredito();
    irPara('compilar', estado.compilar.parada, acender);
  } catch (e) {
    const p = $('#erro-comp');
    p.textContent = e.message;
    p.hidden = false;
    estado.compilar.res = null;
    desenharVeredito();
    irPara('compilar', 'codigo');
    $('#folha-compilar').innerHTML = '<p class="vazio">Um dos arquivos da linguagem tem um erro (mensagem ao lado). Corrija e clique em <b>Compilar</b> de novo.</p>';
  } finally { btn.disabled = false; }
}

function trocarArquivo(arq) {
  $$('#comp-arquivos button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.arq === arq)));
  ['fonte', 'lexico', 'gramatica', 'pr'].forEach((k) => { document.getElementById('ed-comp-' + k).hidden = k !== arq; });
}

/* ================================================================ exemplos */
function preencherSeletor() {
  const sel = $('#exemplo');
  const lista = (estado.exemplos && estado.exemplos[estado.aba]) || [];
  sel.innerHTML = '<option value="">Escolher...</option>' + lista.map((x) => `<option value="${esc(x.id)}">${esc(x.titulo)}</option>`).join('');
}

async function carregarExemplo(aba, id, acender = true) {
  const x = (estado.exemplos[aba] || []).find((e) => e.id === id);
  if (!x) return;
  if (aba === 'lexico') {
    editores['ed-lex-def'].set(x.definicoes);
    editores['ed-lex-fonte'].set(x.entrada);
    $$('#lex-modo button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.modo === x.modo)));
    estado.lexico.execucao = null;
    await lexicoGerar(acender);
    await lexicoAnalisar();
    irPara('lexico', 'tabela', acender);
  } else if (aba === 'sintatico') {
    editores['ed-sin-gram'].set(x.gramatica);
    editores['ed-sin-pr'].set(x.palavras_reservadas);
    editores['ed-sin-tokens'].set(x.tokens);
    await sintaticoGerar(acender);
    if (x.tokens.trim()) await sintaticoAnalisar();
    irPara('sintatico', 'tabela', acender);
  } else {
    editores['ed-comp-fonte'].set(x.fonte);
    editores['ed-comp-lexico'].set(x.lexico);
    editores['ed-comp-gramatica'].set(x.gramatica);
    editores['ed-comp-pr'].set(x.palavras_reservadas);
    trocarArquivo('fonte');
    estado.compilar.parada = 'codigo';
    await compilar(acender);
  }
}

/* ================================================================ início */
async function iniciar() {
  ['ed-lex-def', 'ed-lex-fonte', 'ed-sin-gram', 'ed-sin-pr', 'ed-sin-tokens',
    'ed-comp-fonte', 'ed-comp-lexico', 'ed-comp-gramatica', 'ed-comp-pr'].forEach(criarEditor);

  $$('.abas button').forEach((b) => b.addEventListener('click', () => trocarAba(b.dataset.aba)));
  $('.abas').addEventListener('keydown', (e) => {
    const abas = ['lexico', 'sintatico', 'compilar'];
    const k = abas.indexOf(estado.aba);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      const nova = abas[(k + (e.key === 'ArrowRight' ? 1 : 2)) % 3];
      trocarAba(nova);
      $(`.abas [data-aba=${nova}]`).focus();
    }
  });
  $('#lex-gerar').addEventListener('click', () => lexicoGerar());
  $('#lex-analisar').addEventListener('click', lexicoAnalisar);
  $('#lex-min').addEventListener('change', () => lexicoGerar(false));
  $$('#lex-modo button').forEach((b) => b.addEventListener('click', () => {
    $$('#lex-modo button').forEach((o) => o.setAttribute('aria-checked', String(o === b)));
  }));
  $('#sin-gerar').addEventListener('click', () => sintaticoGerar());
  $('#sin-analisar').addEventListener('click', sintaticoAnalisar);
  $('#comp-compilar').addEventListener('click', () => compilar());
  $$('#comp-arquivos button').forEach((b) => b.addEventListener('click', () => trocarArquivo(b.dataset.arq)));
  $('#exemplo').addEventListener('change', async (e) => {
    if (!e.target.value) return;
    await carregarExemplo(estado.aba, e.target.value);
    e.target.value = '';
  });

  // Ctrl/Cmd + Enter executa a ação principal do editor em foco
  document.addEventListener('keydown', (e) => {
    if (!(e.key === 'Enter' && (e.ctrlKey || e.metaKey))) return;
    const ed = e.target.closest && e.target.closest('.editor');
    if (!ed) return;
    e.preventDefault();
    const id = ed.id;
    if (id === 'ed-lex-def') lexicoGerar();
    else if (id === 'ed-lex-fonte') lexicoAnalisar();
    else if (id === 'ed-sin-gram' || id === 'ed-sin-pr') sintaticoGerar();
    else if (id === 'ed-sin-tokens') sintaticoAnalisar();
    else compilar();
  });

  window.addEventListener('hashchange', () => {
    const a = location.hash.slice(1);
    if (['lexico', 'sintatico', 'compilar'].includes(a) && a !== estado.aba) trocarAba(a);
  });
  ['lexico', 'sintatico', 'compilar'].forEach((aba) => irPara(aba, estado[aba].parada));
  try {
    estado.exemplos = await fetch('/api/exemplos').then((r) => r.json());
  } catch (e) {
    estado.exemplos = { lexico: [], sintatico: [], compilar: [] };
  }
  const inicial = (location.hash || '#lexico').slice(1);
  trocarAba(['lexico', 'sintatico', 'compilar'].includes(inicial) ? inicial : 'lexico');
  await Promise.all([
    carregarExemplo('lexico', '01_enunciado_id_num', false),
    carregarExemplo('sintatico', '01_expressoes_aho', false),
    carregarExemplo('compilar', 'manezes_correto.mane', false),
  ]);
  irPara(estado.aba, estado[estado.aba].parada, true);
}

iniciar();
