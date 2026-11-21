/* MD Launcher — interface (HTML/JS). O backend em Rust cuida de arquivos, rede e emulador. */
'use strict';

const TAURI = window.__TAURI__;
const invoke = (cmd, args) => TAURI.core.invoke(cmd, args);
const win = TAURI.window.getCurrentWindow();
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const S = {
  version: '', settings: {}, games: [], query: '', running: new Set(), wasMax: false,
  fetchTotal: 0, fetchDone: 0, gameModal: null, layers: [], imgVer: {}, selftest: false,
};

// --------------------------------------------------------------------------- utilidades
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = s => String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const year = g => (g.release_date || '').slice(0, 4);
const byId = id => S.games.find(g => g.id === id);
const fileName = p => String(p || '').split(/[\\/]/).pop();

function imgSrc(path, id) {
  if (!path) return '';
  const v = S.imgVer[id] || 0;
  return TAURI.core.convertFileSrc(path) + (v ? `?v=${v}` : '');
}

function fmtPlaytime(sec) {
  sec = Math.floor(sec || 0);
  if (sec < 60) return sec === 0 ? 'Nunca jogado' : 'Menos de 1 min';
  const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60;
  return h === 0 ? `${m} min` : `${h} h ${String(m).padStart(2, '0')} min`;
}
function fmtDate(d) {
  if (!d) return '';
  const p = d.split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : d;
}
function sortGames() { S.games.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())); }
function upsert(g) {
  const i = S.games.findIndex(x => x.id === g.id);
  if (i >= 0) S.games[i] = g; else S.games.push(g);
}

function placeholderHTML(name) {
  return `<div class="ph"><div class="band">MEGA DRIVE</div><div class="nm">${esc(name)}</div></div>`;
}
function coverHTML(g) {
  const src = imgSrc(g.cover_path, g.id);
  return src ? `<img src="${src}" loading="lazy" alt="" draggable="false" onerror="this.style.display='none'">`
    : placeholderHTML(g.name);
}

function toast(text) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = String(text);
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 4500);
}

let statusTimer = null;
function setStatus(text, autoHideMs) {
  const el = $('#status');
  clearTimeout(statusTimer);
  el.textContent = text || '';
  el.hidden = !text;
  if (text && autoHideMs) statusTimer = setTimeout(() => { if (!S.fetchTotal) setStatus(''); }, autoHideMs);
}

// --------------------------------------------------------------------------- grid
function filtered() {
  const terms = norm(S.query).split(/\s+/).filter(Boolean);
  return terms.length ? S.games.filter(g => terms.every(t => norm(g.name).includes(t))) : S.games;
}

function cardHTML(g) {
  const sub = [year(g), g.multiplayer ? 'Multiplayer' : ''].filter(Boolean).join(' · ');
  return `<div class="card" data-id="${g.id}" title="${esc(g.name)}">
    <div class="cover" style="--w:var(--cw);--h:var(--ch)">${coverHTML(g)}</div>
    <div class="t">${esc(g.name)}</div><div class="s">${esc(sub)}</div></div>`;
}

function renderGrid() {
  const list = filtered();
  $('#cards').innerHTML = list.map(cardHTML).join('');
  const empty = $('#empty');
  if (!list.length) {
    empty.textContent = S.query ? `Nenhum jogo encontrado para “${S.query}”.`
      : 'Nenhum jogo ainda.\nUse o botão ⚙ do dock para configurar o emulador e a pasta de ROMs,\nou + para adicionar um jogo manualmente.';
    empty.hidden = false;
  } else empty.hidden = true;
}

function refreshCard(g) {
  const el = $(`.card[data-id="${g.id}"]`);
  if (el) el.outerHTML = cardHTML(g);
}

function setCoverSize(v) {
  document.documentElement.style.setProperty('--cw', `${v}px`);
  const r = $('#size');
  r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
}

// rolagem suave (roda do mouse); touchpad de precisão continua pixel a pixel
const smooth = { target: 0, from: 0, start: 0, raf: 0 };
function setupSmoothScroll() {
  const g = $('#grid');
  const ease = t => 1 - Math.pow(1 - t, 3);
  const tick = now => {
    const t = Math.min(1, (now - smooth.start) / 420);
    g.scrollTop = smooth.from + (smooth.target - smooth.from) * ease(t);
    smooth.raf = t < 1 ? requestAnimationFrame(tick) : 0;
  };
  g.addEventListener('wheel', e => {
    if (e.ctrlKey) return;
    e.preventDefault();
    const touchpad = e.deltaMode === 0 && Math.abs(e.deltaY) < 40 && !Number.isInteger(e.deltaY / 20);
    if (touchpad) { cancelAnimationFrame(smooth.raf); smooth.raf = 0; g.scrollTop += e.deltaY; return; }
    const cellH = parseFloat(getComputedStyle($('.card') || g).height) || 300;
    const step = Math.max(90, cellH * 0.55);
    const notches = e.deltaMode === 1 ? e.deltaY / 3 : e.deltaY / 100;
    const base = smooth.raf ? smooth.target : g.scrollTop;
    const max = g.scrollHeight - g.clientHeight;
    smooth.target = Math.max(0, Math.min(max, base + Math.sign(notches) * Math.max(1, Math.abs(notches)) * step));
    smooth.from = g.scrollTop;
    smooth.start = performance.now();
    if (!smooth.raf) smooth.raf = requestAnimationFrame(tick);
  }, { passive: false });
}

// --------------------------------------------------------------------------- camadas (modais, menu)
function openLayer(cardEl, { dismissable = true, onClose } = {}) {
  const ov = document.createElement('div');
  ov.className = 'overlay';
  ov.appendChild(cardEl);
  $('#layers').appendChild(ov);
  hydrateIcons(ov);
  requestAnimationFrame(() => ov.classList.add('show'));
  const layer = {
    el: ov, card: cardEl, dismissable, closed: false,
    close() {
      if (layer.closed) return;
      layer.closed = true;
      ov.classList.remove('show');
      setTimeout(() => ov.remove(), 170);
      S.layers = S.layers.filter(l => l !== layer);
      onClose && onClose();
    },
  };
  ov.addEventListener('mousedown', e => { if (e.target === ov && layer.dismissable) layer.close(); });
  S.layers.push(layer);
  return layer;
}
const el = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };

function selectHTML(id, options, { lead, value } = {}) {
  const opts = options.map(o => typeof o === 'string' ? { v: o, t: o } : o)
    .map(o => `<option value="${esc(o.v)}" ${String(o.v) === String(value) ? 'selected' : ''}>${esc(o.t)}</option>`).join('');
  return `<div class="select ${lead ? 'has-ico' : ''}">${lead ? `<span class="lead" data-icon="${lead}"></span>` : ''}
    <select id="${id}">${opts}</select><span class="chev" data-icon="chevron"></span></div>`;
}

async function pickFile(filters, defaultPath) {
  const r = await TAURI.dialog.open({ multiple: false, directory: false, filters, defaultPath: defaultPath || undefined });
  return Array.isArray(r) ? r[0] : r;
}
async function pickFiles(filters, defaultPath) {
  const r = await TAURI.dialog.open({ multiple: true, directory: false, filters, defaultPath: defaultPath || undefined });
  return r ? (Array.isArray(r) ? r : [r]) : [];
}
async function pickDir(defaultPath) {
  return TAURI.dialog.open({ directory: true, multiple: false, defaultPath: defaultPath || undefined });
}
const ROM_FILTERS = [{ name: 'ROMs de Mega Drive', extensions: ['md', 'gen', 'smd', 'bin', '68k', 'sgd', 'mdx', 'zip'] }, { name: 'Todos', extensions: ['*'] }];
const EXE_FILTERS = [{ name: 'Executável', extensions: ['exe'] }, { name: 'Todos', extensions: ['*'] }];
const IMG_FILTERS = [{ name: 'Imagens', extensions: ['png', 'jpg', 'jpeg', 'webp'] }];

// campo de caminho com botão "Procurar…"
function pathField(id, value, placeholder = '') {
  return `<div class="row"><input type="text" id="${id}" class="grow" value="${esc(value)}" placeholder="${esc(placeholder)}" spellcheck="false">
    <button class="btn" data-browse="${id}">Procurar…</button></div>`;
}
function bindBrowse(root, handlers) {
  $$('[data-browse]', root).forEach(b => b.addEventListener('click', async () => {
    const id = b.dataset.browse, input = $('#' + id, root);
    const p = await handlers[id](input.value);
    if (p) { input.value = p; input.dispatchEvent(new Event('input')); }
  }));
}

// --------------------------------------------------------------------------- emuladores
const PROFILES = [
  { key: 'retroarch', label: 'RetroArch', fs: '-f', tpl: '-L "cores\\genesis_plus_gx_libretro.dll" {fullscreen} "{rom}"', note: 'Troque o core no modelo se usar PicoDrive ou BlastEm (ex.: picodrive_libretro.dll).' },
  { key: 'fusion', label: 'Kega Fusion', fs: '-fullscreen', tpl: '-gen -auto {fullscreen} "{rom}"', note: 'Em tela cheia, ESC fecha o emulador.' },
  { key: 'blastem', label: 'BlastEm', fs: '-f', tpl: '{fullscreen} "{rom}"', note: '-f ALTERNA o modo: se o blastem.cfg já estiver em fullscreen, ele abre em janela.' },
  { key: 'ares', label: 'ares', fs: '--fullscreen', tpl: '--system "Mega Drive" {fullscreen} "{rom}"', note: '' },
  { key: 'mednafen', label: 'Mednafen', fs: '-video.fs 1', tpl: '{fullscreen} "{rom}"', note: '' },
  { key: 'gens', label: 'Gens/GS', fs: '--fs --quickexit', tpl: '{fullscreen} "{rom}"', note: '--quickexit faz o ESC fechar o emulador. O Gens 2.x antigo pode ignorar esses argumentos.' },
  { key: 'dgen', label: 'DGen', fs: '-f', tpl: '{fullscreen} "{rom}"', note: '' },
  { key: 'exodus', label: 'Exodus', fs: '', tpl: '"{rom}"', note: 'Exodus não tem argumento de tela cheia.' },
];
function detectProfile(path) {
  const stem = fileName(path).replace(/\.[^.]+$/, '').toLowerCase();
  return PROFILES.find(p => stem.includes(p.key) || (p.key === 'fusion' && stem.includes('kega')));
}
function profileText(path) {
  if (!path) return '';
  const p = detectProfile(path);
  if (!p) return 'Emulador não reconhecido — tudo bem, funciona com qualquer um. Se ele tiver argumento de tela cheia, informe abaixo.';
  return `Detectado: <b>${p.label}</b> · tela cheia: ${p.fs ? `<code>${esc(p.fs)}</code>` : 'nenhum'}.${p.note ? ' ' + esc(p.note) : ''}`;
}

function emulatorFieldsHTML(s) {
  return `<div class="grid2">
    <label>Emulador (.exe)</label>${pathField('f-exe', s.emulator_path, 'C:\\Emuladores\\...\\emulador.exe')}
    <div class="full hint" id="f-exe-info">${profileText(s.emulator_path)}</div>
    <label>Modelo de argumentos</label><input type="text" id="f-tpl" value="${esc(s.launch_template)}" placeholder='{fullscreen} "{rom}"' spellcheck="false">
    <label>Argumento de tela cheia</label><input type="text" id="f-fs" value="${esc(s.fullscreen_args)}" placeholder="ex.: -fullscreen, -f, --fullscreen" spellcheck="false">
    <div class="full hint"><code>{rom}</code> vira o caminho da ROM e <code>{fullscreen}</code> vira o argumento de tela cheia quando o botão estiver ligado. Presets:
      ${PROFILES.map(p => `${p.label} <code>${esc(p.fs || '—')}</code>`).join(', ')}.</div>
  </div>`;
}
function bindEmulatorFields(root, s) {
  let last = s.emulator_path;
  bindBrowse(root, { 'f-exe': v => pickFile(EXE_FILTERS, v) });
  $('#f-exe', root).addEventListener('input', e => {
    const path = e.target.value.trim();
    $('#f-exe-info', root).innerHTML = profileText(path);
    const p = detectProfile(path);
    if (p && path !== last) { $('#f-tpl', root).value = p.tpl; $('#f-fs', root).value = p.fs; }
    last = path;
  });
}
function applyEmulatorFields(root, s) {
  s.emulator_path = $('#f-exe', root).value.trim();
  s.launch_template = $('#f-tpl', root).value.trim() || '"{rom}"';
  s.fullscreen_args = $('#f-fs', root).value.trim();
}

const LINK_SGDB = 'https://www.steamgriddb.com/profile/preferences/api';
const LINK_IGDB = 'https://api-docs.igdb.com/#account-creation';
function keyFieldsHTML(s) {
  return `<div class="grid2">
    <label>SteamGridDB</label><input type="password" id="k-sgdb" value="${esc(s.sgdb_key)}" placeholder="Chave da API do SteamGridDB" spellcheck="false">
    <div class="full hint">Capas e heroes. Pegue sua chave grátis em <a href="#" data-url="${LINK_SGDB}">steamgriddb.com › Preferências › API</a>.</div>
    <label>IGDB Client ID</label><input type="text" id="k-cid" value="${esc(s.igdb_client_id)}" placeholder="Client ID (Twitch)" spellcheck="false">
    <label>IGDB Secret</label><input type="password" id="k-sec" value="${esc(s.igdb_client_secret)}" placeholder="Client Secret (Twitch)" spellcheck="false">
    <div class="full hint">Opcional: data de lançamento, multiplayer e artes extras. <a href="#" data-url="${LINK_IGDB}">Como criar (Twitch Developers)</a>.
      Sem chaves, o launcher ainda busca capas no Libretro Thumbnails.</div>
  </div>`;
}
function bindLinks(root) {
  $$('[data-url]', root).forEach(a => a.addEventListener('click', e => { e.preventDefault(); invoke('open_url', { url: a.dataset.url }); }));
}
function applyKeyFields(root, s) {
  s.sgdb_key = $('#k-sgdb', root).value.trim();
  s.igdb_client_id = $('#k-cid', root).value.trim();
  s.igdb_client_secret = $('#k-sec', root).value.trim();
}
async function saveSettings() { await invoke('save_settings', { settings: S.settings }); }

// --------------------------------------------------------------------------- biblioteca
async function rescan(silent) {
  if (!S.settings.rom_folders?.length) return;
  setStatus('Procurando ROMs…');
  try {
    const r = await invoke('scan');
    S.games = r.games; sortGames(); renderGrid();
    setStatus(r.new_count ? `${r.new_count} jogo(s) novo(s)` : '', silent ? 0 : 2500);
    const pending = S.games.filter(g => !g.metadata_done).map(g => g.id);
    if (pending.length) fetchMetadata(pending, false);
    else if (!r.new_count) setStatus('');
  } catch (e) { setStatus(`Erro ao escanear: ${e}`, 5000); }
}

async function fetchMetadata(ids, force) {
  S.fetchTotal += ids.length;
  updateFetchStatus();
  const queue = [...ids];
  const worker = async () => {
    while (queue.length) {
      const id = queue.shift();
      try {
        const g = await invoke('auto_fetch', { id, force });
        S.imgVer[g.id] = (S.imgVer[g.id] || 0) + 1;
        upsert(g); refreshCard(g);
        if (S.gameModal && S.gameModal.game.id === g.id) S.gameModal.refresh(g);
      } catch (e) { /* segue para o próximo */ }
      S.fetchDone++;
      updateFetchStatus();
    }
  };
  await Promise.all([0, 1, 2, 3].map(worker));
}
function updateFetchStatus() {
  if (S.fetchDone >= S.fetchTotal) {
    S.fetchTotal = S.fetchDone = 0;
    setStatus('Capas atualizadas ✓', 3000);
  } else setStatus(`Baixando capas e informações… ${S.fetchDone}/${S.fetchTotal}`);
}

// --------------------------------------------------------------------------- jogar
const fullscreenFor = g => g.fullscreen == null ? !!S.settings.fullscreen_default : !!g.fullscreen;

async function play(g, fullscreen) {
  if (S.running.has(g.id)) return;
  try {
    const ng = await invoke('play', { id: g.id, fullscreen });
    upsert(ng);
    S.running.add(g.id);
    if (S.gameModal && S.gameModal.game.id === g.id) S.gameModal.setRunning(true);
    if (S.settings.minimize_on_play) {
      S.wasMax = await win.isMaximized();
      setTimeout(() => win.minimize(), 400);
    }
  } catch (e) { toast(e); }
}

async function onGameFinished({ id, game }) {
  S.running.delete(id);
  if (game) { upsert(game); refreshCard(game); }
  if (S.gameModal && S.gameModal.game.id === id) { S.gameModal.setRunning(false); if (game) S.gameModal.refresh(game); }
  if (!S.running.size && await win.isMinimized()) {
    // volta exatamente como estava quando o Play foi dado (maximizada ou não)
    await win.unminimize();
    if (S.wasMax && !(await win.isMaximized())) await win.maximize();
    await win.setFocus();
  }
}

// --------------------------------------------------------------------------- modal do jogo
function openGame(g) {
  const card = el(`<div class="mcard gm">
    <div class="hero"></div>
    <button class="x" title="Fechar (Esc)"><span data-icon="close"></span></button>
    <div class="gcover"></div>
    <div class="credits"></div>
    <div class="info">
      <h1></h1><div class="chips"></div><div class="pt"></div>
      <div class="actions">
        <button class="btn play"><span data-icon="play"></span><span class="lbl">JOGAR</span></button>
        <button class="btn toggle" title="Iniciar o jogo em tela cheia (usa o argumento do seu emulador)"><span data-icon="fullscreen"></span>Tela cheia</button>
        <button class="btn icon" title="Editar informações, capa, hero, ROM e emulador"><span data-icon="edit"></span></button>
      </div>
    </div></div>`);
  const layer = openLayer(card, { onClose: () => { if (S.gameModal === m) S.gameModal = null; } });
  const fsBtn = $('.btn.toggle', card), playBtn = $('.btn.play', card);
  const m = {
    game: g, layer,
    refresh(ng) {
      if (ng) m.game = ng;
      const g = m.game;
      const hero = $('.hero', card);
      const heroSrc = imgSrc(g.hero_path, g.id), coverSrc = imgSrc(g.cover_path, g.id);
      hero.className = 'hero' + (!heroSrc && !coverSrc ? ' grid' : '');
      hero.innerHTML = heroSrc ? `<img src="${heroSrc}" alt="">` : coverSrc ? `<img class="blur" src="${coverSrc}" alt="">` : '';
      $('.gcover', card).innerHTML = coverSrc ? `<img src="${coverSrc}" alt="">` : placeholderHTML(g.name);
      $('h1', card).textContent = g.name;
      const chips = [];
      if (g.release_date) chips.push(['calendar', fmtDate(g.release_date)]);
      if (g.multiplayer === true) chips.push(['users', `Multiplayer${g.players ? ` · ${g.players} jogadores` : ''}`]);
      else if (g.multiplayer === false) chips.push(['user', 'Single player']);
      if (g.developer) chips.push(['cart', g.developer]);
      $('.chips', card).innerHTML = chips.map(([i, t]) => `<span class="chip">${icon(i)}${esc(t)}</span>`).join('');
      let pt = `<b>${fmtPlaytime(g.playtime)}</b> ${g.playtime >= 60 ? 'jogadas' : ''}`;
      if (g.last_played) pt += `&nbsp;&nbsp;<span class="last">· última vez em ${new Date(g.last_played * 1000).toLocaleDateString('pt-BR')}</span>`;
      $('.pt', card).innerHTML = pt;
      $('.credits', card).textContent = [g.cover_source && `Capa: ${g.cover_source}`, g.hero_source && `Hero: ${g.hero_source}`].filter(Boolean).join('   ·   ');
    },
    setRunning(on) {
      playBtn.disabled = on;
      $('.lbl', playBtn).textContent = on ? 'JOGANDO…' : 'JOGAR';
    },
  };
  fsBtn.classList.toggle('on', fullscreenFor(g));
  fsBtn.addEventListener('click', async () => {
    const on = !fsBtn.classList.contains('on');
    fsBtn.classList.toggle('on', on);
    m.game.fullscreen = on;
    try { upsert(await invoke('update_game', { game: m.game })); } catch (e) { toast(e); }
  });
  playBtn.addEventListener('click', () => play(m.game, fsBtn.classList.contains('on')));
  $('.btn.icon', card).addEventListener('click', () => openEdit(m.game));
  $('.x', card).addEventListener('click', () => layer.close());
  S.gameModal = m;
  m.refresh();
  m.setRunning(S.running.has(g.id));
  hydrateIcons(card);
  return m;
}

// --------------------------------------------------------------------------- modal de edição
function openEdit(g, isNew = false) {
  const h = Math.floor((g.playtime || 0) / 3600), mi = Math.floor((g.playtime || 0) / 60) % 60;
  const multi = g.multiplayer === true ? 'sim' : g.multiplayer === false ? 'nao' : '';
  const card = el(`<div class="mcard em">
    <div class="mhead"><div class="tt"><h2>${isNew ? 'Adicionar jogo' : 'Editar jogo'}</h2><div class="sub">${esc(fileName(g.rom_path))}</div></div>
      <button class="btn ghost icon x"><span data-icon="close"></span></button></div>
    <div class="body scroll">
      <div class="left">
        <div class="section">Informações</div>
        <div class="form">
          <label>Nome</label><input type="text" id="e-name" value="${esc(g.name)}" spellcheck="false">
          <label>Lançamento</label><input type="text" id="e-date" value="${esc(g.release_date)}" placeholder="AAAA-MM-DD">
          <label>Multiplayer</label>${selectHTML('e-multi', [{ v: '', t: 'Desconhecido' }, { v: 'sim', t: 'Sim' }, { v: 'nao', t: 'Não' }], { value: multi })}
          <label>Jogadores</label><input type="text" id="e-players" value="${esc(g.players)}" placeholder="ex.: 1-2">
          <label>Desenvolvedora</label><input type="text" id="e-dev" value="${esc(g.developer)}" spellcheck="false">
          <label>Tempo jogado</label><div class="row"><input type="number" id="e-h" min="0" value="${h}" class="grow"><span>h</span>
            <input type="number" id="e-m" min="0" max="59" value="${mi}" class="grow"><span>min</span></div>
        </div>
        <div class="section">Arquivos</div>
        <div class="form">
          <label>ROM / ZIP</label>${pathField('e-rom', g.rom_path)}
          <label>Emulador</label>${pathField('e-emu', g.emulator_override, 'Padrão das configurações')}
          <label>Argumentos</label><input type="text" id="e-tpl" value="${esc(g.template_override)}" placeholder="${esc(S.settings.launch_template || '"{rom}"')}" spellcheck="false">
        </div>
        <div class="hint">Deixe <b>Emulador</b> e <b>Argumentos</b> vazios para usar o padrão. Use <code>{rom}</code> e <code>{fullscreen}</code> no modelo.</div>
      </div>
      <div class="right">
        <div class="section">Capa e hero</div>
        <div class="row" style="align-items:flex-start;gap:14px">
          <div style="display:flex;flex-direction:column;gap:8px"><div class="pv-cover"></div><button class="btn" id="e-cov-local">Arquivo local…</button></div>
          <div style="flex:1;display:flex;flex-direction:column;gap:8px;min-width:0"><div class="pv-hero"></div>
            <div class="row"><button class="btn" id="e-hero-local">Arquivo local…</button><button class="btn ghost" id="e-hero-clear">Remover hero</button></div></div>
        </div>
        <div class="section">Buscar em</div>
        <div class="row">
          <div style="width:190px;flex:none">${selectHTML('e-src', [{ v: 'SteamGridDB', t: 'SteamGridDB' + (S.settings.sgdb_key ? '' : ' (sem chave)') },
            { v: 'IGDB', t: 'IGDB' + (S.settings.igdb_client_id && S.settings.igdb_client_secret ? '' : ' (sem chave)') }, { v: 'Libretro', t: 'Libretro' }],
            { lead: 'database', value: S.settings.sgdb_key ? 'SteamGridDB' : (S.settings.igdb_client_id ? 'IGDB' : 'Libretro') })}</div>
          <input type="text" id="e-q" class="grow" value="${esc(g.name)}" placeholder="Nome do jogo" spellcheck="false">
          <button class="btn primary" id="e-search"><span data-icon="search"></span>Buscar</button>
        </div>
        <div class="row">
          <div class="grow">${selectHTML('e-cand', [{ v: '', t: 'Os resultados aparecem aqui — clique para trocar' }], { lead: 'list' })}</div>
          <button class="btn" id="e-apply" disabled title="Copia data de lançamento, multiplayer, jogadores e desenvolvedora deste resultado">Usar data e multiplayer</button>
        </div>
        <div class="status-line" id="e-status"></div>
        <div>Capas</div><div class="strip covers" id="e-covers"></div>
        <div>Heroes</div><div class="strip heroes" id="e-heroes"></div>
      </div>
    </div>
    <div class="mfoot">
      ${isNew ? '' : '<button class="btn danger" id="e-remove"><span data-icon="trash"></span><span class="lbl">Remover da biblioteca</span></button>'}
      <span class="grow"></span>
      <button class="btn" id="e-cancel">Cancelar</button>
      <button class="btn primary" id="e-save" style="width:130px">Salvar</button>
    </div></div>`);
  const layer = openLayer(card);
  const st = { selCover: null, selHero: null, cands: [], token: 0, confirm: false };
  const status = t => { $('#e-status', card).textContent = t; };
  const candSel = $('#e-cand', card);
  candSel.disabled = true;

  const showCover = (src) => { $('.pv-cover', card).innerHTML = src ? `<img src="${src}" alt="">` : placeholderHTML($('#e-name', card).value); };
  const showHero = (src) => { $('.pv-hero', card).innerHTML = src ? `<img src="${src}" alt="">` : 'sem hero'; };
  showCover(imgSrc(g.cover_path, g.id));
  showHero(imgSrc(g.hero_path, g.id));

  bindBrowse(card, { 'e-rom': v => pickFile(ROM_FILTERS, v), 'e-emu': v => pickFile(EXE_FILTERS, v) });
  $('.x', card).addEventListener('click', () => layer.close());
  $('#e-cancel', card).addEventListener('click', () => layer.close());
  $('#e-cov-local', card).addEventListener('click', async () => {
    const p = await pickFile(IMG_FILTERS); if (!p) return;
    st.selCover = { path: p }; showCover(TAURI.core.convertFileSrc(p));
  });
  $('#e-hero-local', card).addEventListener('click', async () => {
    const p = await pickFile(IMG_FILTERS); if (!p) return;
    st.selHero = { path: p }; showHero(TAURI.core.convertFileSrc(p));
  });
  $('#e-hero-clear', card).addEventListener('click', () => { st.selHero = { clear: true }; showHero(''); });

  const fillStrip = (box, arts, kind) => {
    box.innerHTML = arts.map((a, i) => `<div class="thumb" data-i="${i}" title="${a.width ? `${a.width}×${a.height}` : esc(a.source)}">
      <img src="${esc(a.thumb)}" loading="lazy" alt="" referrerpolicy="no-referrer"></div>`).join('');
    $$('.thumb', box).forEach(t => t.addEventListener('click', () => {
      $$('.thumb', box).forEach(x => x.classList.remove('sel'));
      t.classList.add('sel');
      const a = arts[+t.dataset.i];
      if (kind === 'cover') { st.selCover = { url: a.url, source: a.source }; showCover(a.thumb); }
      else { st.selHero = { url: a.url, source: a.source }; showHero(a.thumb); }
    }));
  };

  const loadArts = async (i) => {
    const c = st.cands[i]; if (!c) return;
    $('#e-apply', card).disabled = !(c.release_date || c.multiplayer != null || c.developer);
    const tok = ++st.token;
    $('#e-covers', card).innerHTML = ''; $('#e-heroes', card).innerHTML = '';
    status(`Carregando imagens de “${c.name}”…`);
    try {
      const r = await invoke('get_arts', { candidate: c });
      if (tok !== st.token) return;
      status(`${r.covers.length} capa(s) e ${r.heroes.length} hero(es). Clique para escolher.`);
      fillStrip($('#e-covers', card), r.covers.slice(0, 40), 'cover');
      fillStrip($('#e-heroes', card), r.heroes.slice(0, 30), 'hero');
    } catch (e) { if (tok === st.token) status(`Erro: ${e}`); }
  };
  candSel.addEventListener('change', () => loadArts(+candSel.value));

  const search = async () => {
    const source = $('#e-src', card).value;
    const keyed = source === 'Libretro' || (source === 'SteamGridDB' ? S.settings.sgdb_key : (S.settings.igdb_client_id && S.settings.igdb_client_secret));
    if (!keyed) { status(`Adicione a chave do ${source} em Configurações para buscar aqui.`); return; }
    const term = $('#e-q', card).value.trim() || g.name;
    const tok = ++st.token;
    status(`Buscando “${term}” no ${source}…`);
    candSel.innerHTML = '<option>Buscando…</option>'; candSel.disabled = true;
    $('#e-covers', card).innerHTML = ''; $('#e-heroes', card).innerHTML = '';
    try {
      const res = await invoke('search', { source, term, id: g.id });
      if (tok !== st.token) return;
      st.cands = res || [];
      if (!st.cands.length) {
        candSel.innerHTML = '<option>Nada encontrado</option>';
        status('Nada encontrado. Tente outro nome (ex.: sem subtítulo).'); return;
      }
      status(`${st.cands.length} resultado(s) no ${source}.`);
      const nt = norm(term).replace(/[^a-z0-9]/g, '');
      let best = st.cands.findIndex(c => norm(c.name).replace(/[^a-z0-9]/g, '') === nt);
      if (best < 0) best = 0;
      candSel.innerHTML = st.cands.map((c, i) => `<option value="${i}" ${i === best ? 'selected' : ''}>${esc(c.name)}${c.release_date ? ` (${c.release_date.slice(0, 4)})` : ''}</option>`).join('');
      candSel.disabled = st.cands.length < 1;
      loadArts(best);
    } catch (e) { if (tok === st.token) { status(`Erro: ${e}`); candSel.innerHTML = '<option>Erro na busca</option>'; } }
  };
  $('#e-search', card).addEventListener('click', search);
  $('#e-q', card).addEventListener('keydown', e => { if (e.key === 'Enter') search(); });

  $('#e-apply', card).addEventListener('click', () => {
    const c = st.cands[+candSel.value]; if (!c) return;
    if (c.release_date) $('#e-date', card).value = c.release_date;
    if (c.multiplayer != null) $('#e-multi', card).value = c.multiplayer ? 'sim' : 'nao';
    if (c.players) $('#e-players', card).value = c.players;
    if (c.developer) $('#e-dev', card).value = c.developer;
    status('Dados aplicados — clique em Salvar para confirmar.');
  });

  const rm = $('#e-remove', card);
  rm && rm.addEventListener('click', async () => {
    if (!st.confirm) { st.confirm = true; $('.lbl', rm).textContent = 'Clique de novo para confirmar'; return; }
    await removeGame(g); layer.close();
  });

  $('#e-save', card).addEventListener('click', async () => {
    const btn = $('#e-save', card);
    btn.disabled = true; btn.textContent = 'Salvando…';
    const cur = byId(g.id) || g;
    const ng = {
      ...cur,
      name: $('#e-name', card).value.trim() || cur.name,
      release_date: $('#e-date', card).value.trim(),
      multiplayer: { '': null, sim: true, nao: false }[$('#e-multi', card).value],
      players: $('#e-players', card).value.trim(),
      developer: $('#e-dev', card).value.trim(),
      playtime: (parseInt($('#e-h', card).value) || 0) * 3600 + Math.min(59, parseInt($('#e-m', card).value) || 0) * 60 + ((cur.playtime || 0) % 60),
      rom_path: $('#e-rom', card).value.trim() || cur.rom_path,
      emulator_override: $('#e-emu', card).value.trim(),
      template_override: $('#e-tpl', card).value.trim(),
    };
    try {
      let saved = await invoke('update_game', { game: ng });
      for (const [kind, sel] of [['cover', st.selCover], ['hero', st.selHero]]) {
        if (!sel) continue;
        saved = await invoke('apply_art', { id: g.id, kind, url: sel.url || null, path: sel.path || null, source: sel.source || null });
        S.imgVer[g.id] = (S.imgVer[g.id] || 0) + 1;
      }
      upsert(saved); sortGames(); renderGrid();
      if (S.gameModal && S.gameModal.game.id === g.id) S.gameModal.refresh(saved);
      layer.close();
    } catch (e) {
      btn.disabled = false; btn.textContent = 'Salvar';
      status(`Não consegui salvar: ${e}`);
    }
  });
  if (isNew && (S.settings.sgdb_key || S.settings.igdb_client_id)) setTimeout(search, 50);
  return layer;
}

async function removeGame(g) {
  try {
    await invoke('remove_game', { id: g.id });
    S.games = S.games.filter(x => x.id !== g.id);
    if (S.gameModal && S.gameModal.game.id === g.id) S.gameModal.layer.close();
    renderGrid();
  } catch (e) { toast(e); }
}

// --------------------------------------------------------------------------- configurações
function openSettings() {
  const s = { ...S.settings, rom_folders: [...(S.settings.rom_folders || [])] };
  const card = el(`<div class="mcard stm">
    <div class="mhead"><div class="tt"><h2>Configurações</h2><div class="sub">MD Launcher ${esc(S.version)}</div></div>
      <button class="btn ghost icon x"><span data-icon="close"></span></button></div>
    <div class="body scroll">
      <div class="section">Emulador</div>
      ${emulatorFieldsHTML(s)}
      <label class="check"><input type="checkbox" id="c-fsdef" ${s.fullscreen_default ? 'checked' : ''}>Tela cheia ligada por padrão em jogos novos</label>
      <label class="check"><input type="checkbox" id="c-min" ${s.minimize_on_play ? 'checked' : ''}>Minimizar o launcher enquanto o jogo roda</label>
      <label class="check"><input type="checkbox" id="c-zip" ${s.extract_zip ? 'checked' : ''}>Extrair ROMs de .zip antes de abrir (para emuladores que não leem zip)</label>
      <div class="section">Pastas de ROMs</div>
      <div class="folders" id="c-folders"></div>
      <div class="row"><button class="btn" id="c-add">Adicionar pasta…</button><button class="btn" id="c-rm">Remover selecionada</button>
        <span class="grow"></span><label class="check"><input type="checkbox" id="c-sub" ${s.scan_subfolders ? 'checked' : ''}>Incluir subpastas</label></div>
      <div class="section">Capas e informações</div>
      ${keyFieldsHTML(s)}
      <div class="section">Biblioteca</div>
      <div class="row" style="flex-wrap:wrap">
        <button class="btn" id="c-rescan"><span data-icon="refresh"></span>Reescanear pastas</button>
        <button class="btn" id="c-missing"><span data-icon="image"></span>Buscar artes que faltam</button>
        <button class="btn" id="c-all" title="Busca de novo capa, hero e dados de todos os jogos (substitui as artes atuais)">Rebaixar tudo</button>
        <button class="btn" id="c-data">Pasta de dados</button>
      </div>
    </div>
    <div class="mfoot"><span class="grow"></span><button class="btn" id="c-cancel">Cancelar</button>
      <button class="btn primary" id="c-save" style="width:130px">Salvar</button></div></div>`);
  const layer = openLayer(card);
  let selFolder = -1;
  const drawFolders = () => {
    $('#c-folders', card).innerHTML = s.rom_folders.map((f, i) => `<div data-i="${i}" class="${i === selFolder ? 'sel' : ''}">${esc(f)}</div>`).join('');
    $$('#c-folders div', card).forEach(d => d.addEventListener('click', () => { selFolder = +d.dataset.i; drawFolders(); }));
  };
  drawFolders();
  bindEmulatorFields(card, s);
  bindLinks(card);
  $('#c-add', card).addEventListener('click', async () => { const p = await pickDir(); if (p && !s.rom_folders.includes(p)) { s.rom_folders.push(p); drawFolders(); } });
  $('#c-rm', card).addEventListener('click', () => { if (selFolder >= 0) { s.rom_folders.splice(selFolder, 1); selFolder = -1; drawFolders(); } });
  const save = async () => {
    const old = JSON.stringify([S.settings.rom_folders, S.settings.scan_subfolders]);
    applyEmulatorFields(card, s); applyKeyFields(card, s);
    s.fullscreen_default = $('#c-fsdef', card).checked;
    s.minimize_on_play = $('#c-min', card).checked;
    s.extract_zip = $('#c-zip', card).checked;
    s.scan_subfolders = $('#c-sub', card).checked;
    S.settings = { ...S.settings, ...s };
    await saveSettings();
    return old !== JSON.stringify([s.rom_folders, s.scan_subfolders]);
  };
  $('.x', card).addEventListener('click', () => layer.close());
  $('#c-cancel', card).addEventListener('click', () => layer.close());
  $('#c-save', card).addEventListener('click', async () => { const changed = await save(); layer.close(); if (changed) rescan(false); });
  $('#c-rescan', card).addEventListener('click', async () => { await save(); rescan(false); });
  $('#c-missing', card).addEventListener('click', async () => { await save(); fetchMetadata(S.games.filter(g => !g.cover_path || !g.hero_path).map(g => g.id), false); });
  $('#c-all', card).addEventListener('click', async () => { await save(); fetchMetadata(S.games.map(g => g.id), true); });
  $('#c-data', card).addEventListener('click', () => invoke('open_data_dir').catch(toast));
  return layer;
}

// --------------------------------------------------------------------------- assistente inicial
function openWizard() {
  const s = { ...S.settings, rom_folders: [...(S.settings.rom_folders || [])] };
  const card = el(`<div class="mcard wz">
    <div class="steps"><span>Boas-vindas</span><span>Emulador</span><span>ROMs</span><span>Capas</span></div>
    <div class="page" data-p="0" style="align-items:center;justify-content:center;text-align:center">
      <div class="brand">MD Launcher</div>
      <div style="color:var(--muted);font-size:15px;margin-top:8px">Sua coleção de Mega Drive com cara de biblioteca de verdade.</div>
      <div class="hint" style="margin-top:18px;max-width:560px">Em três passos: escolha o emulador, aponte a pasta das suas ROMs e (opcional) cole a chave do SteamGridDB para baixar capas e heroes automaticamente.</div>
    </div>
    <div class="page" data-p="1"><h3>Qual emulador vai rodar os jogos?</h3>
      <div class="lead-t">Qualquer emulador de Mega Drive serve: RetroArch, Kega Fusion, BlastEm, ares, Gens…</div>${emulatorFieldsHTML(s)}</div>
    <div class="page" data-p="2"><h3>Onde estão suas ROMs?</h3>
      <div class="lead-t">Arquivos .md, .gen, .smd, .bin e também .zip com a ROM dentro.</div>
      ${pathField('w-roms', s.rom_folders[0] || '')}
      <label class="check"><input type="checkbox" id="w-sub" ${s.scan_subfolders ? 'checked' : ''}>Incluir subpastas</label>
      <div id="w-count" style="font-size:14px"></div></div>
    <div class="page" data-p="3"><h3>Capas, heroes e informações</h3>
      <div class="lead-t">Cole sua chave do SteamGridDB. O IGDB é opcional e traz data e multiplayer.</div>${keyFieldsHTML(s)}</div>
    <div class="mfoot"><button class="btn" id="w-back">Voltar</button><span class="grow"></span>
      <button class="btn primary" id="w-next" style="width:150px">Começar</button></div></div>`);
  const layer = openLayer(card, { dismissable: false });
  let page = 0, countTok = 0;
  const go = i => {
    page = Math.max(0, Math.min(3, i));
    $$('.page', card).forEach(p => { p.hidden = +p.dataset.p !== page; });
    $('#w-back', card).style.visibility = page > 0 ? 'visible' : 'hidden';
    $('#w-next', card).textContent = ['Começar', 'Avançar', 'Avançar', 'Concluir'][page];
    $$('.steps span', card).forEach((sp, n) => { sp.className = n === page ? 'on' : n < page ? 'done' : ''; });
  };
  const count = async () => {
    const path = $('#w-roms', card).value.trim();
    const out = $('#w-count', card);
    if (!path) { out.textContent = ''; return; }
    out.textContent = 'Procurando ROMs…';
    const tok = ++countTok;
    try {
      const n = await invoke('count_roms', { folder: path, recursive: $('#w-sub', card).checked });
      if (tok !== countTok) return;
      out.innerHTML = n ? `<b style="color:#7ee787">${n} jogo(s) de Mega Drive encontrados</b>`
        : '<span style="color:var(--warn)">Nenhuma ROM de Mega Drive nessa pasta.</span>';
    } catch (e) { out.textContent = String(e); }
  };
  bindEmulatorFields(card, s);
  bindBrowse(card, { 'w-roms': v => pickDir(v) });
  bindLinks(card);
  $('#w-roms', card).addEventListener('input', count);
  $('#w-roms', card).addEventListener('change', count);
  $('#w-sub', card).addEventListener('change', count);
  $('#w-back', card).addEventListener('click', () => go(page - 1));
  $('#w-next', card).addEventListener('click', async () => {
    if (page === 1 && !$('#f-exe', card).value.trim()) {
      $('#f-exe-info', card).innerHTML = '<span style="color:var(--warn)">Escolha o .exe do emulador para continuar.</span>'; return;
    }
    if (page === 2 && !$('#w-roms', card).value.trim()) {
      $('#w-count', card).innerHTML = '<span style="color:var(--warn)">Escolha a pasta das ROMs.</span>'; return;
    }
    if (page < 3) { go(page + 1); return; }
    applyEmulatorFields(card, s); applyKeyFields(card, s);
    const folder = $('#w-roms', card).value.trim();
    s.rom_folders = [folder, ...s.rom_folders.filter(f => f !== folder)];
    s.scan_subfolders = $('#w-sub', card).checked;
    s.first_run_done = true;
    S.settings = { ...S.settings, ...s };
    await saveSettings();
    layer.close();
    rescan(false);
  });
  go(0);
  if (s.rom_folders[0]) count();
  return layer;
}

// --------------------------------------------------------------------------- menu de contexto
let ctxMenu = null;
function closeMenu() { if (ctxMenu) { ctxMenu.remove(); ctxMenu = null; } }
function contextMenu(g, x, y) {
  closeMenu();
  const items = [
    ['play', 'Jogar', () => play(g, fullscreenFor(g))],
    [null, 'Detalhes', () => openGame(g)],
    ['edit', 'Editar…', () => openEdit(g)],
    ['folder', 'Mostrar ROM no Explorer', () => invoke('open_path', { path: g.rom_path }).catch(toast)],
    ['refresh', 'Buscar artes de novo', () => fetchMetadata([g.id], true)],
    '-',
    ['trash', 'Remover da biblioteca', () => removeGame(g)],
  ];
  const m = document.createElement('div');
  m.className = 'menu';
  m.innerHTML = items.map((it, i) => it === '-' ? '<hr>' : `<button data-i="${i}">${it[0] ? icon(it[0]) : '<span style="width:15px"></span>'}${it[1]}</button>`).join('');
  document.body.appendChild(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 8) + 'px';
  m.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  $$('button', m).forEach(b => b.addEventListener('click', () => { const it = items[+b.dataset.i]; closeMenu(); it[2](); }));
  ctxMenu = m;
}

// --------------------------------------------------------------------------- dock
async function addGames() {
  const files = await pickFiles(ROM_FILTERS, S.settings.rom_folders?.[0]);
  if (!files.length) return;
  try {
    const added = await invoke('add_files', { paths: files });
    if (!added.length) return;
    added.forEach(upsert); sortGames(); renderGrid();
    const pending = added.filter(g => !g.metadata_done).map(g => g.id);
    if (added.length === 1) openEdit(added[0], true);
    if (pending.length) fetchMetadata(pending, false);
  } catch (e) { toast(e); }
}

// --------------------------------------------------------------------------- janela
async function syncMax() {
  const m = await win.isMaximized();
  document.body.classList.toggle('max', m);
  $('#btn-max').title = m ? 'Restaurar' : 'Maximizar';
  $('#btn-max').innerHTML = m
    ? '<svg viewBox="0 0 10 10"><rect x=".5" y="2.5" width="7" height="7"/><path d="M2.5 2.5V.5h7v7h-2"/></svg>'
    : '<svg viewBox="0 0 10 10"><rect x=".5" y=".5" width="9" height="9"/></svg>';
}

function bindChrome() {
  $('#btn-min').addEventListener('click', () => win.minimize());
  $('#btn-max').addEventListener('click', () => win.toggleMaximize());
  $('#btn-close').addEventListener('click', () => win.close());
  $$('.rz').forEach(r => r.addEventListener('mousedown', e => { if (e.button === 0) win.startResizeDragging(r.dataset.dir); }));
  win.onResized(() => syncMax());
  syncMax();

  const search = $('#search'), clear = $('#search-clear');
  search.addEventListener('input', () => {
    S.query = search.value; clear.hidden = !search.value;
    $('#grid').scrollTop = 0; renderGrid();
  });
  search.addEventListener('keydown', e => { if (e.key === 'Escape') { search.value = ''; search.dispatchEvent(new Event('input')); search.blur(); e.stopPropagation(); } });
  clear.addEventListener('click', () => { search.value = ''; search.dispatchEvent(new Event('input')); search.focus(); });

  const size = $('#size');
  let sizeTimer = null;
  size.value = S.settings.cover_size || 180;
  setCoverSize(+size.value);
  size.addEventListener('input', () => {
    const g = $('#grid'), frac = g.scrollTop / Math.max(1, g.scrollHeight - g.clientHeight);
    setCoverSize(+size.value);
    g.scrollTop = frac * (g.scrollHeight - g.clientHeight);
    S.settings.cover_size = +size.value;
    clearTimeout(sizeTimer); sizeTimer = setTimeout(saveSettings, 400);
  });
  $('#d-add').addEventListener('click', addGames);
  $('#d-emu').addEventListener('click', () => invoke('open_emulator').catch(toast));
  $('#d-roms').addEventListener('click', () => {
    if (!S.settings.rom_folders?.length) return toast('Nenhuma pasta de ROMs configurada.');
    invoke('open_path', { path: S.settings.rom_folders[0] }).catch(toast);
  });
  $('#d-cfg').addEventListener('click', openSettings);

  $('#cards').addEventListener('click', e => {
    const c = e.target.closest('.card'); if (!c) return;
    const g = byId(c.dataset.id); if (g) openGame(g);
  });
  $('#cards').addEventListener('contextmenu', e => {
    const c = e.target.closest('.card'); if (!c) return;
    e.preventDefault();
    const g = byId(c.dataset.id); if (g) contextMenu(g, e.clientX, e.clientY);
  });
  document.addEventListener('contextmenu', e => { if (!e.target.closest('input, textarea')) e.preventDefault(); });
  document.addEventListener('mousedown', e => { if (ctxMenu && !ctxMenu.contains(e.target)) closeMenu(); });
  $('#grid').addEventListener('scroll', closeMenu);
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); search.focus(); search.select(); return; }
    if (e.key === 'Escape') {
      if (ctxMenu) return closeMenu();
      const top = S.layers[S.layers.length - 1];
      if (top && top.dismissable) top.close();
    }
    // impede atalhos de navegador (recarregar, imprimir, zoom) dentro do app
    if (e.key === 'F5' || ((e.ctrlKey || e.metaKey) && ['r', 'p', '+', '-', '=', '0'].includes(e.key.toLowerCase()))) e.preventDefault();
  });
}

// --------------------------------------------------------------------------- autoteste (CI)
async function selftest() {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  try {
    const g = S.games[0] || { id: 'selftest', name: 'Self Test', rom_path: 'selftest.md', playtime: 0 };
    for (const open of [() => openGame(g).layer, () => openEdit(g), () => openSettings(), () => openWizard()]) {
      const l = open(); await wait(250); l.close(); await wait(200);
    }
    if (!$('#dock') || !$('#logo')) throw new Error('interface incompleta');
    await invoke('selftest_done', { ok: true });
  } catch (e) {
    console.error(e);
    await invoke('selftest_done', { ok: false });
  }
}

// --------------------------------------------------------------------------- início
async function init() {
  hydrateIcons();
  const st = await invoke('get_state');
  S.version = st.version; S.settings = st.settings; S.games = st.games; S.selftest = st.selftest;
  sortGames();
  bindChrome();
  setupSmoothScroll();
  renderGrid();
  TAURI.event.listen('game-finished', e => onGameFinished(e.payload));
  if (S.selftest) return selftest();
  if (!S.settings.first_run_done) setTimeout(openWizard, 250);
  else rescan(true);
}

window.addEventListener('DOMContentLoaded', () => init().catch(e => toast(`Erro ao iniciar: ${e}`)));
