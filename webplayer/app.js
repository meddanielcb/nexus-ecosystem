(() => {
  "use strict";

  const PROXY_BASE = "/stream";
  const PAIR_BASE = "/pair";

  // ---------------- Elementos DOM ----------------
  const els = {
    loginGate: document.getElementById("loginGate"),
    appShell: document.getElementById("appShell"),
    playerLayer: document.getElementById("playerLayer"),
    playerWrap: document.getElementById("playerWrap"),
    screen: document.getElementById("screen"),
    nav: document.querySelector("nav"),
    video: document.getElementById("video"),
    inUser: document.getElementById("inUser"),
    inPass: document.getElementById("inPass"),
    btnLogin: document.getElementById("btnLogin"),
    btnLogout: document.getElementById("btnLogout"),
    loginErr: document.getElementById("loginErr"),
    qrCodeImg: document.getElementById("qrCodeImg"),
    qrPinCode: document.getElementById("qrPinCode"),
    btnProfile: document.getElementById("btnProfile"),
    btnMotionToggle: document.getElementById("btnMotionToggle"),
    footUser: document.getElementById("footUser"),
    clock: document.getElementById("clock"),
    clockDate: document.getElementById("clockDate"),
    btnPlayerBack: document.getElementById("btnPlayerBack"),
    btnPlayerFav: document.getElementById("btnPlayerFav"),
    btnPlayerEpg: document.getElementById("btnPlayerEpg"),
    btnZoom: document.getElementById("btnZoom"),
    btnFullscreen: document.getElementById("btnFullscreen"),
    zoomToast: document.getElementById("zoomToast"),
    overlay: document.getElementById("overlay"),
    overlayTitle: document.getElementById("overlayTitle"),
    overlayMsg: document.getElementById("overlayMsg"),
    notice: document.getElementById("notice"),
    adCornerBadge: document.getElementById("adCornerBadge"),
    adLowerThird: document.getElementById("adLowerThird"),
    btnAdLtClose: document.getElementById("btnAdLtClose"),
    adBbImgLink: document.getElementById("adBbImgLink")
  };

  // ---------------- Estado Global ----------------
  let session = null;
  let allStreams = [];
  let allCategories = [];
  let vodCategories = [];
  let seriesCategories = [];
  let vodCache = {}; // category_id -> streams
  let seriesCache = {}; // category_id -> series
  let seriesInfoCache = {}; // series_id -> info
  let activeStreamId = null;
  let selectedItem = null;
  let hls = null;
  let tsPlayer = null;
  let pairPollTimer = null;
  let isTvMode = false;
  let reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Estado de Navegação da Interface (Designer Engine)
  const glyph = {
    back: 'M15 5L8 12 15 19',
    next: 'M9 5L16 12 9 19',
    play: 'M8 4L21 12 8 20Z',
    star: 'M12 2L15 8 22 9 17 14 18 22 12 18 6 22 7 14 2 9 9 8Z',
    home: 'M3 11L12 3 21 11V21H15V14H9V21H3Z',
    sports: 'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 4a6 6 0 1 1-6 6 6 6 0 0 1 6-6z'
  };
  const icon = k => `<svg viewBox="0 0 24 24" class="icon" aria-hidden="true" style="width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;"><path d="${glyph[k] || glyph.play}"/></svg>`;
  const safe = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let state = {
    view: 'home',
    kind: 'movie', // 'movie' | 'series' | 'sports'
    category: 'Todos',
    categoryId: '',
    page: 0,
    title: null,
    season: 1,
    query: ''
  };
  let stack = [];
  let focusMemory = '';
  let transitionBack = false;

  // Favoritos persistidos
  let savedFavs = [];
  try {
    savedFavs = JSON.parse(localStorage.getItem('nexus_lab_favorites') || '[]');
    if (!Array.isArray(savedFavs)) savedFavs = [];
  } catch (e) {
    savedFavs = [];
  }

  function capacity() {
    return innerWidth < 600 ? (innerHeight < 550 ? 2 : 4) : (innerHeight < 650 || innerWidth < 900 ? 4 : 6);
  }

  function notice(text) {
    if (!els.notice) return;
    els.notice.textContent = text;
    els.notice.classList.add("visible");
    setTimeout(() => els.notice.classList.remove("visible"), 3500);
  }

  function showOverlay(title, msg) {
    if (!els.overlay) return;
    if (els.overlayTitle) els.overlayTitle.textContent = title;
    if (els.overlayMsg) els.overlayMsg.textContent = msg || "";
    els.overlay.classList.remove("hidden");
  }

  function hideOverlay() {
    if (els.overlay) els.overlay.classList.add("hidden");
  }

  // ---------------- Navegação de Telas ----------------
  function go(next) {
    transitionBack = false;
    stack.push({ state: { ...state }, focus: document.activeElement?.dataset?.key });
    state = { ...state, ...next, page: 0 };
    draw();
  }

  function back() {
    transitionBack = true;
    if (stack.length) {
      const prev = stack.pop();
      state = prev.state;
      focusMemory = prev.focus;
      draw();
    } else {
      state.view = 'home';
      draw();
    }
  }

  function paging(total) {
    const pages = Math.max(1, Math.ceil(total / capacity()));
    return `<div class="paging">
      <button data-act="prev" ${state.page === 0 ? 'disabled' : ''} aria-label="Página anterior">${icon('back')}</button>
      <span>${state.page + 1} / ${pages}</span>
      <button data-act="next" ${state.page >= pages - 1 ? 'disabled' : ''} aria-label="Próxima página">${icon('next')}</button>
    </div>`;
  }

  function topBar(title, sub = '') {
    return `<div class="tv-title">
      <div><span class="eyebrow">${sub}</span><h1>${title}</h1></div>
      <button data-act="back">${icon('back')} Voltar</button>
    </div>`;
  }

  // ---------------- Renderizadores de Views ----------------

  // 1. HOME (Bento Cinematográfico do Designer)
  function homeView() {
    const liveCount = allStreams.length || "24.000+";
    return `<section class="tv-home">
      <img class="scenery" src="assets/stadium-cinema.webp" alt="">
      <video class="ambient-video" muted loop playsinline preload="none" data-src="assets/stadium-motion.mp4" aria-hidden="true" tabindex="-1" hidden></video>
      <div class="stadium-lights" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="home-copy">
        <span class="eyebrow">Nexus / O seu lugar na primeira fila</span>
        <h1>A noite.<br>O jogo.<br>O seu play.</h1>
        <p>Mais de ${liveCount} canais em 4K, filmes de cinema e séries completas.</p>
        <button class="primary" data-act="live" data-key="home-live">${icon('play')} Abrir TV ao vivo</button>
      </div>
      <div class="destinations">
        <button class="destination" data-act="live" data-key="home-live-dest">
          <img src="assets/live-cinema.webp" alt="">
          <span>01</span>
          <strong>TV ao vivo</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="sports" data-key="home-sports">
          <img src="assets/stadium-cinema.webp" alt="">
          <span>02</span>
          <strong>Jogos do Dia</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="movie" data-key="home-movies">
          <img src="assets/movies-cinema.webp" alt="">
          <span>03</span>
          <strong>Filmes</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="series" data-key="home-series">
          <img src="assets/series-cinema.webp" alt="">
          <span>04</span>
          <strong>Séries</strong>
          ${icon('next')}
        </button>
      </div>
    </section>`;
  }

  // 2. CATEGORIAS (Pastas / Folders)
  function categoriesView() {
    let cats = [];
    let title = "Categorias";
    let sub = "Escolha para navegar";

    if (state.kind === 'movie') {
      cats = vodCategories.length ? vodCategories : [{ category_id: "557", category_name: "Lançamentos Cinema" }];
      title = "Cine Nexus";
      sub = "Catálogo de Filmes / Escolha o Gênero";
    } else if (state.kind === 'series') {
      cats = seriesCategories.length ? seriesCategories : [{ category_id: "7837", category_name: "Séries em Destaque" }];
      title = "Mais um episódio.";
      sub = "Séries / Escolha uma Categoria";
    } else if (state.kind === 'sports') {
      cats = allCategories.filter(c => {
        const n = (c.category_name || '').toLowerCase();
        return n.includes('esporte') || n.includes('jogo') || n.includes('futebol') || n.includes('premiere') || n.includes('conmebol');
      });
      title = "Arena Esportiva";
      sub = "Transmissões e Confrontos";
    }

    const paged = cats.slice(state.page * capacity(), (state.page + 1) * capacity());
    return `${topBar(title, sub)}
    <div class="folder-grid">
      ${paged.map((c, i) => `
        <button class="folder" data-cat-id="${c.category_id}" data-cat-name="${c.category_name}" data-key="cat-${c.category_id}">
          <span class="eyebrow">${String(state.page * capacity() + i + 1).padStart(2, '0')}</span>
          <strong>${c.category_name}</strong>
          <span>Explorar ${icon('next')}</span>
        </button>
      `).join('')}
    </div>
    ${paging(cats.length)}`;
  }

  // 3. CATÁLOGO DE PÔSTERES (VOD / Filmes e Séries)
  function catalogView() {
    const list = getCatalogItems();
    const typeLabel = state.kind === 'series' ? 'Séries' : 'Filmes';

    return `${topBar(state.category || 'Catálogo', `${typeLabel} / Grade de Títulos`)}
    <div class="tv-search">
      <input id="tvSearch" type="search" value="${safe(state.query)}" placeholder="Buscar neste catálogo…" aria-label="Buscar neste catálogo">
      <span>${list.length} títulos disponíveis</span>
    </div>
    <div class="poster-grid">
      ${list.slice(state.page * capacity(), (state.page + 1) * capacity()).map(t => {
        const cover = t.stream_icon || t.cover || "design/posters/dune.webp";
        const yr = t.year || t.rating || "HD";
        return `
          <button class="tv-poster" data-item-id="${t.stream_id || t.series_id}" data-item-type="${state.kind}" data-key="item-${t.stream_id || t.series_id}">
            <img src="${cover}" loading="lazy" onerror="this.onerror=null;this.src='design/posters/dune.webp';" alt="">
            <strong>${(t.name || 'Título').replace(/</g, '&lt;')}</strong>
            <small>${yr} · ${state.category}</small>
          </button>
        `;
      }).join('') || '<p class="empty">Nenhum título encontrado.</p>'}
    </div>
    ${paging(list.length)}`;
  }

  function getCatalogItems() {
    let raw = [];
    if (state.kind === 'movie') {
      raw = vodCache[state.categoryId] || [];
    } else if (state.kind === 'series') {
      raw = seriesCache[state.categoryId] || [];
    }
    if (!state.query) return raw;
    const q = state.query.toLowerCase();
    return raw.filter(item => (item.name || '').toLowerCase().includes(q));
  }

  // 4. FICHA TÉCNICA (Detail View)
  function detailView() {
    const t = selectedItem;
    if (!t) return `<div class="empty">Item não encontrado.<br><button data-act="back">Voltar</button></div>`;

    const cover = t.backdrop_path && t.backdrop_path[0] ? t.backdrop_path[0] : (t.stream_icon || t.cover || "assets/stadium-cinema.webp");
    const title = (t.name || "Título").replace(/</g, '&lt;');
    const plot = t.plot || "Assista a esta superprodução em alta definição na Nexus PlayTV com streaming offshore sem travamentos.";
    const meta = `${t.year || '2025'} · ${t.genre || 'Cinema'} · Nota ${t.rating || '8.5'}`;

    return `<section class="tv-detail">
      <img class="scenery" src="${cover}" onerror="this.onerror=null;this.src='assets/stadium-cinema.webp';" alt="">
      <button class="detail-back" data-act="back">${icon('back')} Voltar</button>
      <div class="detail-copy">
        <span class="eyebrow">${meta}</span>
        <h1>${title}</h1>
        <p>${plot}</p>
        <button class="primary" data-act="${state.kind === 'series' ? 'load-seasons' : 'play-movie'}" data-key="detail-primary">
          ${icon('play')} ${state.kind === 'series' ? 'Escolher temporada' : 'Assistir filme'}
        </button>
      </div>
    </section>`;
  }

  // 5. TEMPORADAS & EPISÓDIOS
  function seasonsView() {
    const seasons = (selectedItem && selectedItem.seasons) || [1];
    return `${topBar('Temporadas', `Série / ${(selectedItem && selectedItem.name) || ''}`)}
    <div class="folder-grid">
      ${seasons.map((s, i) => `
        <button class="folder" data-season-num="${s.season_number || i + 1}" data-key="season-${s.season_number || i + 1}">
          <span class="eyebrow">Temporada Completa</span>
          <strong>Temporada ${s.season_number || i + 1}</strong>
          <span>Ver episódios ${icon('next')}</span>
        </button>
      `).join('')}
    </div>`;
  }

  function episodesView() {
    const eps = (selectedItem && selectedItem.episodes && selectedItem.episodes[String(state.season)]) || [];
    return `${topBar(`Temporada ${state.season}`, 'Episódios em Alta Definição')}
    <div class="folder-grid">
      ${eps.slice(state.page * capacity(), (state.page + 1) * capacity()).map((ep, i) => `
        <button class="folder" data-episode-id="${ep.id || ep.stream_id}" data-episode-title="${ep.title || 'Episódio ' + (i + 1)}" data-episode-ext="${ep.container_extension || 'mp4'}" data-key="ep-${ep.id || i}">
          <span class="eyebrow">Episódio ${ep.episode_num || i + 1}</span>
          <strong>${(ep.title || 'Episódio ' + (i + 1)).replace(/</g, '&lt;')}</strong>
          <span>Assistir ${icon('play')}</span>
        </button>
      `).join('') || '<p class="empty">Nenhum episódio cadastrado nesta temporada.</p>'}
    </div>
    ${paging(eps.length)}`;
  }

  // 6. TV AO VIVO (Grade de Canais com Pastas)
  function liveView() {
    let list = allStreams;
    if (state.view === 'favorites') {
      list = allStreams.filter(c => savedFavs.includes(String(c.stream_id)));
    } else if (state.view === 'sports') {
      list = allStreams.filter(c => {
        const n = String(c.name || '').toLowerCase();
        const catN = String(c.category_name || '').toLowerCase();
        return n.includes(' x ') || n.includes(' vs ') || /\b\d{1,2}:\d{2}\b/.test(n) || catN.includes('esporte') || catN.includes('premiere') || catN.includes('sportv') || catN.includes('espn');
      });
    }

    if (state.query) {
      const q = state.query.toLowerCase();
      list = list.filter(c => (c.name || '').toLowerCase().includes(q));
    }

    const title = state.view === 'favorites' ? 'Minha Lista de Favoritos' : (state.view === 'sports' ? 'Jogos de Hoje & Esportes' : 'TV ao Vivo');
    const paged = list.slice(state.page * capacity(), (state.page + 1) * capacity());

    return `${topBar(title, 'Canais / Selecione para Sintonizar')}
    <div class="tv-search">
      <input id="tvSearch" type="search" value="${safe(state.query)}" placeholder="Buscar canal ou partida…" aria-label="Buscar canal">
      <span>${list.length} canais encontrados</span>
    </div>
    <div class="folder-grid">
      ${paged.map((c, i) => {
        const num = c.num ? String(c.num).padStart(3, '0') : String(state.page * capacity() + i + 1).padStart(3, '0');
        const logo = c.stream_icon ? toProxied(c.stream_icon) : "design/nexus.svg";
        const isFav = savedFavs.includes(String(c.stream_id));
        return `
          <button class="folder channel-folder" data-channel-id="${c.stream_id}" data-channel-name="${c.name || 'Canal'}" data-key="chan-${c.stream_id}">
            <span class="eyebrow">${num} ${isFav ? '★' : ''}</span>
            <span class="channel-logo-plate">
              <img src="${logo}" loading="lazy" onerror="this.onerror=null;this.src='design/nexus.svg';" alt="">
            </span>
            <strong>${(c.name || 'Canal').replace(/</g, '&lt;')}</strong>
            <span>Abrir canal ${icon('play')}</span>
          </button>
        `;
      }).join('') || '<p class="empty">Nenhum canal encontrado.</p>'}
    </div>
    ${paging(list.length)}`;
  }

  // 7. CONTA & STATUS
  function accountView() {
    const u = session ? session.user : "Visitante";
    return `${topBar('Sua Conta', 'Nexus PlayTV / Status')}
    <div class="empty" style="text-align:left;max-width:600px;margin:20px auto;line-height:2;">
      <p><strong>Usuário:</strong> ${u}</p>
      <p><strong>Status:</strong> <span style="color:#b7ff3c;">● Assinatura Ativa</span></p>
      <p><strong>Servidor:</strong> Offshore Suécia (Njalla BBR Turbo)</p>
      <p><strong>Conexões Ativas:</strong> 1 tela em uso</p>
      <br>
      <button data-act="back">${icon('back')} Voltar</button>
    </div>`;
  }

  // Cache de EPG
  let epgCache = {}; // channel_name -> epg_data

  async function fetchEpgData(name, iconUrl) {
    if (!name) return null;
    const cacheKey = `${name}|${iconUrl || ''}`;
    if (epgCache[cacheKey]) return epgCache[cacheKey];
    try {
      const url = `/beta/api/epg?name=${encodeURIComponent(name)}&icon=${encodeURIComponent(iconUrl || '')}`;
      const res = await fetch(url);
      if (!res.ok) return null;
      const data = await res.json();
      epgCache[cacheKey] = data;
      return data;
    } catch (e) {
      return null;
    }
  }

  // 8. EPG (Programação em Tempo Real)
  function epgView() {
    const s = allStreams.find(c => String(c.stream_id) === String(activeStreamId));
    const name = s ? s.name : "Canal Selecionado";
    const logo = s && s.stream_icon ? toProxied(s.stream_icon) : "design/nexus.svg";
    const cacheKey = `${name}|${(s && s.stream_icon) || ''}`;
    const epg = epgCache[cacheKey];

    if (!epg) {
      // Dispara busca assíncrona e renderiza carregando
      fetchEpgData(name, s ? s.stream_icon : "").then(data => {
        if (state.view === 'epg') draw();
      });

      return `${topBar('Guia de Programação', name)}
      <div class="empty" style="line-height:2;">
        <div class="spinner" style="width:30px;height:30px;border:3px solid rgba(183,255,60,0.2);border-top-color:#b7ff3c;border-radius:50%;margin:20px auto;animation:spin 0.8s linear infinite;"></div>
        <p style="font-size:16px;color:#fff;">Consultando guia de programação em tempo real…</p>
        <button data-act="back-to-player">${icon('play')} Voltar ao Player</button>
      </div>`;
    }

    const cur = epg.current || {};
    const upcoming = epg.upcoming || [];

    return `${topBar('Guia de Programação (EPG)', name)}
    <div class="epg-container" style="display:flex;flex-direction:column;gap:18px;max-width:1050px;margin:0 auto;width:100%;padding:10px 0;">
      <!-- Bloco do Programa Atual -->
      <div class="epg-current-card" style="background:rgba(20,26,22,0.85);border:1px solid rgba(183,255,60,0.35);border-radius:14px;padding:22px;display:flex;gap:20px;align-items:flex-start;backdrop-filter:blur(10px);">
        <img src="${logo}" style="width:64px;height:64px;object-fit:contain;background:#101416;border-radius:10px;padding:6px;border:1px solid rgba(255,255,255,0.08);flex-shrink:0;" alt="">
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
            <span style="background:#ff5252;color:#fff;font-size:10px;font-weight:800;padding:2px 7px;border-radius:4px;letter-spacing:1px;">● NO AR AGORA</span>
            <span style="font-family:'Space Grotesk',monospace;font-size:14px;color:#b7ff3c;font-weight:700;">${cur.start || '--:--'} - ${cur.stop || '--:--'}</span>
          </div>
          <h2 style="font-size:22px;color:#fff;margin:0 0 8px 0;font-weight:700;">${(cur.title || 'Transmissão ao Vivo').replace(/</g, '&lt;')}</h2>
          <p style="font-size:13px;color:#a2aca0;line-height:1.6;margin:0 0 14px 0;">${(cur.desc || 'Assista em alta definição na Nexus PlayTV.').replace(/</g, '&lt;')}</p>
          
          <!-- Barra de Progresso -->
          <div style="width:100%;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;">
            <div style="width:${cur.progress || 0}%;height:100%;background:#b7ff3c;border-radius:3px;transition:width 0.3s ease;"></div>
          </div>
        </div>
      </div>

      <!-- Próximos Programas -->
      <div style="display:flex;flex-direction:column;gap:10px;">
        <span style="font-size:11px;font-weight:700;color:#8f9a90;text-transform:uppercase;letter-spacing:1px;">A Seguir na Programação</span>
        <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));gap:12px;">
          ${upcoming.map(item => `
            <div style="background:rgba(12,16,14,0.7);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:6px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-family:'Space Grotesk',monospace;color:#b7ff3c;font-size:12px;font-weight:700;">${item.start}</span>
                <span style="font-size:10px;color:#6f7a70;">até ${item.stop}</span>
              </div>
              <strong style="font-size:14px;color:#f0f4ee;">${(item.title || 'Programa').replace(/</g, '&lt;')}</strong>
              <p style="font-size:11px;color:#8f9a90;line-height:1.4;margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">${(item.desc || '').replace(/</g, '&lt;')}</p>
            </div>
          `).join('') || '<p style="color:#7f8a80;font-size:12px;">Nenhum próximo programa cadastrado na grade.</p>'}
        </div>
      </div>

      <div style="margin-top:10px;">
        <button data-act="back-to-player" class="primary">${icon('play')} Voltar ao Canal ao Vivo</button>
      </div>
    </div>`;
  }

  // ---------------- Render Principal ----------------
  function draw(keepInput = false) {
    if (!els.screen) return;
    const oldVideo = els.screen.querySelector('.ambient-video');
    if (oldVideo) oldVideo.pause();

    document.body.classList.toggle('home-view', state.view === 'home');
    document.body.classList.toggle('motion-off', reduced);

    // Atualiza nav ativa
    document.querySelectorAll("nav button").forEach(b => {
      const act = b.getAttribute("data-act");
      b.classList.toggle("active", act === state.view || (act === 'movie' && state.kind === 'movie') || (act === 'series' && state.kind === 'series'));
    });

    let viewHtml = homeView();
    if (state.view === 'home') viewHtml = homeView();
    else if (state.view === 'categories') viewHtml = categoriesView();
    else if (state.view === 'catalog') viewHtml = catalogView();
    else if (state.view === 'detail') viewHtml = detailView();
    else if (state.view === 'seasons') viewHtml = seasonsView();
    else if (state.view === 'episodes') viewHtml = episodesView();
    else if (state.view === 'live' || state.view === 'favorites' || state.view === 'sports') viewHtml = liveView();
    else if (state.view === 'account') viewHtml = accountView();
    else if (state.view === 'epg') viewHtml = epgView();

    els.screen.innerHTML = viewHtml;
    syncAmbient();

    if (!keepInput && !reduced && els.screen.animate) {
      els.screen.getAnimations().forEach(a => a.cancel());
      els.screen.animate([
        { opacity: 0.15, transform: `translateX(${transitionBack ? -12 : 18}px)` },
        { opacity: 1, transform: 'translateX(0)' }
      ], { duration: 240, easing: 'cubic-bezier(.16,1,.3,1)' });
    }

    if (keepInput) {
      const inp = document.getElementById("tvSearch");
      if (inp) { inp.focus(); inp.selectionStart = inp.selectionEnd = inp.value.length; }
      return;
    }

    const target = [...els.screen.querySelectorAll('[data-key]')].find(e => e.dataset.key === focusMemory) || els.screen.querySelector('button:not(:disabled)');
    focusMemory = '';
    requestAnimationFrame(() => target?.focus());
  }

  // ---------------- Player Engine (MPEG-TS & HLS) ----------------
  function playStream(streamId, label) {
    destroyPlayer();
    activeStreamId = streamId;

    if (els.playerLayer) els.playerLayer.classList.remove("hidden");
    showOverlay("Carregando canal…", label || "");

    const video = els.video;
    const user = session ? session.user : "";
    const pass = session ? session.pass : "";
    const tsUrl = toProxied(apiUrl(`/live/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${streamId}.ts`));

    // Atualiza botão de favoritos no player
    updatePlayerFavButton();

    if (window.mpegts && window.mpegts.isSupported()) {
      try {
        tsPlayer = window.mpegts.createPlayer({
          type: 'mse',
          isLive: true,
          url: tsUrl
        }, {
          enableWorker: true,
          lazyLoad: false,
          liveBufferLatencyChasing: false,
          liveBufferLatencyMaxLatency: 15.0,
          liveBufferLatencyMinRemain: 4.0,
          autoCleanupSourceBuffer: true,
          stashInitialSize: 1536 * 1024
        });

        tsPlayer.attachMediaElement(video);
        tsPlayer.load();

        let playStarted = false;
        const startPlayback = () => {
          if (playStarted) return;
          playStarted = true;
          hideOverlay();
          video.controls = true;
          showSkyOsd(streamId, label);

          // Anúncios transitórios oficiais PixGet
          setTimeout(() => showLowerThird(10000), 6000);
          startCornerBadgeLoop();

          const playPromise = video.play();
          if (playPromise !== undefined) {
            playPromise.catch(err => {
              if (err.name === "NotAllowedError") {
                video.muted = true;
                video.play().catch(() => {});
                notice("Toque na tela para ativar o áudio");
                const unmute = () => {
                  video.muted = false;
                  window.removeEventListener("click", unmute);
                };
                window.addEventListener("click", unmute, { once: true });
              }
            });
          }
        };

        tsPlayer.on(window.mpegts.Events.MEDIA_INFO, startPlayback);
        video.onloadeddata = startPlayback;
        video.oncanplay = startPlayback;

        tsPlayer.on(window.mpegts.Events.ERROR, (errType, errDetail) => {
          console.warn("[TS Error] Fallback para HLS:", errType, errDetail);
          fallbackHls(toProxied(apiUrl(`/live/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${streamId}.m3u8`)), label);
        });

        return;
      } catch (err) {
        console.warn("[TS Catch] Fallback para HLS:", err);
      }
    }

    fallbackHls(toProxied(apiUrl(`/live/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${streamId}.m3u8`)), label);
  }

  function fallbackHls(finalUrl, label) {
    destroyPlayer();
    const video = els.video;

    if (window.Hls && window.Hls.isSupported()) {
      hls = new window.Hls({
        enableWorker: true,
        lowLatencyMode: true,
        liveSyncDurationCount: 3,
        manifestLoadingMaxRetry: 3
      });
      hls.loadSource(finalUrl);
      hls.attachMedia(video);

      hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        hideOverlay();
        video.controls = true;
        showSkyOsd(activeStreamId, label);
        video.play().catch(() => {
          video.muted = true;
          video.play().catch(() => {});
        });
      });

      hls.on(window.Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          showOverlay("Reconectando canal…", "Buscando melhor rota de transmissão.");
          setTimeout(() => playStream(activeStreamId, label), 3000);
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = finalUrl;
      video.controls = true;
      video.play().then(hideOverlay).catch(hideOverlay);
    }
  }

  function playVodMedia(url, name) {
    destroyPlayer();
    if (els.playerLayer) els.playerLayer.classList.remove("hidden");
    showOverlay("Reproduzindo…", name);

    const video = els.video;
    video.src = toProxied(url);
    video.controls = true;
    showSkyOsd(999, name);

    video.play().then(hideOverlay).catch(() => {
      video.muted = true;
      video.play().then(hideOverlay).catch(hideOverlay);
    });
  }

  function destroyPlayer() {
    if (hls) { try { hls.destroy(); } catch (e) {} hls = null; }
    if (tsPlayer) {
      try {
        tsPlayer.pause();
        tsPlayer.unload();
        tsPlayer.detachMediaElement();
        tsPlayer.destroy();
      } catch (e) {}
      tsPlayer = null;
    }
    if (els.video) {
      try {
        els.video.controls = false;
        els.video.pause();
        els.video.removeAttribute("src");
        els.video.load();
      } catch (e) {}
    }
  }

  function closePlayer() {
    destroyPlayer();
    if (els.playerLayer) els.playerLayer.classList.add("hidden");
  }

  // ---------------- OSD Banner Estilo Sky / BTV ----------------
  function showSkyOsd(streamId, label) {
    const osd = document.getElementById("skyChannelOsd");
    if (!osd) return;
    const stream = allStreams.find(s => String(s.stream_id) === String(streamId));
    const numEl = document.getElementById("osdNum");
    const logoEl = document.getElementById("osdLogo");
    const nameEl = document.getElementById("osdName");
    const resEl = document.getElementById("osdRes");
    const progEl = document.getElementById("osdProgTitle");

    const index = allStreams.findIndex(s => String(s.stream_id) === String(streamId));
    const numStr = stream && stream.num ? String(stream.num).padStart(3, "0") : String(index >= 0 ? index + 1 : 1).padStart(3, "0");
    if (numEl) numEl.textContent = numStr;

    if (logoEl) {
      logoEl.src = stream && stream.stream_icon ? toProxied(stream.stream_icon) : "design/nexus.svg";
      logoEl.onerror = () => { logoEl.src = "design/nexus.svg"; };
    }

    const cleanName = (label || (stream && stream.name) || "Nexus PlayTV").replace(/</g, "&lt;");
    if (nameEl) nameEl.innerHTML = cleanName;

    const is4k = /4k|uhd/i.test(label || (stream && stream.name) || "");
    const isFhd = /fhd|1080/i.test(label || (stream && stream.name) || "");
    if (resEl) {
      resEl.textContent = is4k ? "4K" : (isFhd ? "FHD" : "HD");
      resEl.className = `osd-res ${is4k ? "res-4k" : (isFhd ? "res-fhd" : "")}`;
    }

    if (progEl) {
      progEl.textContent = stream && stream.category_name ? `${stream.category_name} • Transmissão ao Vivo` : "Transmissão Oficial Nexus";
      // Busca assíncrona do EPG real para atualizar o OSD
      fetchEpgData(label || (stream && stream.name), stream && stream.stream_icon).then(epg => {
        if (epg && epg.found && epg.current && epg.current.title) {
          progEl.innerHTML = `<strong>${epg.current.title}</strong> (${epg.current.start} - ${epg.current.stop})`;
        }
      });
    }

    osd.classList.add("show");
    if (window.skyOsdTimer) clearTimeout(window.skyOsdTimer);
    window.skyOsdTimer = setTimeout(() => osd.classList.remove("show"), 4500);
  }

  function updatePlayerFavButton() {
    if (!els.btnPlayerFav) return;
    const isFav = savedFavs.includes(String(activeStreamId));
    els.btnPlayerFav.setAttribute("aria-pressed", isFav ? "true" : "false");
    const favLabel = document.getElementById("favLabel");
    if (favLabel) favLabel.textContent = isFav ? "Salvo" : "Favoritar";
  }

  function toggleActiveFavorite() {
    if (!activeStreamId) return;
    const strId = String(activeStreamId);
    if (savedFavs.includes(strId)) {
      savedFavs = savedFavs.filter(id => id !== strId);
      notice("Removido dos favoritos");
    } else {
      savedFavs.push(strId);
      notice("Canal salvo nos favoritos");
    }
    localStorage.setItem('nexus_lab_favorites', JSON.stringify(savedFavs));
    updatePlayerFavButton();
  }

  // ---------------- Zoom Mode (YouTube Style) ----------------
  function showZoomToast(text) {
    if (!els.zoomToast) return;
    els.zoomToast.textContent = text;
    els.zoomToast.classList.add("show");
    if (window.zoomToastTimer) clearTimeout(window.zoomToastTimer);
    window.zoomToastTimer = setTimeout(() => els.zoomToast.classList.remove("show"), 1200);
  }

  function toggleZoom() {
    if (!els.playerWrap) return;
    const isZoomed = els.playerWrap.classList.toggle("zoom-fill");
    localStorage.setItem("nexus_zoom_mode", isZoomed ? "fill" : "fit");
    showZoomToast(isZoomed ? "⛶ Ampliado para preencher a tela" : "⊡ Ajustado à tela (original)");
  }

  if (localStorage.getItem("nexus_zoom_mode") === "fill" && els.playerWrap) {
    els.playerWrap.classList.add("zoom-fill");
  }

  // ---------------- Fullscreen ----------------
  function toggleFullscreen() {
    if (!els.playerWrap) return;
    const isFull = !!document.fullscreenElement || !!document.webkitFullscreenElement;
    if (!isFull) {
      const req = els.playerWrap.requestFullscreen || els.playerWrap.webkitRequestFullscreen || els.playerWrap.msRequestFullscreen;
      if (req) req.call(els.playerWrap).catch(() => {});
    } else {
      const exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
      if (exit) exit.call(document).catch(() => {});
    }
  }

  // ---------------- Publicidade Oficial PixGet ----------------
  let badgeLoopActive = false;
  function startCornerBadgeLoop() {
    if (badgeLoopActive || !els.adCornerBadge) return;
    badgeLoopActive = true;
    function cycleBadge() {
      els.adCornerBadge.classList.add("visible");
      setTimeout(() => {
        els.adCornerBadge.classList.remove("visible");
        setTimeout(cycleBadge, 35000); // 35 segundos invisível
      }, 14000); // 14 segundos visível
    }
    setTimeout(cycleBadge, 4000);
  }

  let ltTimer = null;
  function showLowerThird(durationMs = 10000) {
    if (!els.adLowerThird) return;
    els.adLowerThird.classList.add("active");
    if (ltTimer) clearTimeout(ltTimer);
    ltTimer = setTimeout(() => {
      els.adLowerThird.classList.remove("active");
      ltTimer = null;
    }, durationMs);
  }

  function hideLowerThird() {
    if (els.adLowerThird) els.adLowerThird.classList.remove("active");
    if (ltTimer) { clearTimeout(ltTimer); ltTimer = null; }
  }

  if (els.btnAdLtClose) {
    els.btnAdLtClose.addEventListener("click", e => {
      e.stopPropagation();
      hideLowerThird();
    });
  }

  // Billboard Vertical (Rail Lateral no Catálogo/Canais)
  function startBillboardLoop() {
    if (!els.adBbImgLink) return;
    function cycleBillboard() {
      els.adBbImgLink.classList.add("visible");
      setTimeout(() => {
        els.adBbImgLink.classList.remove("visible");
        setTimeout(cycleBillboard, 22000); // 22s apagado
      }, 12000); // 12s visível
    }
    setTimeout(cycleBillboard, 1500);
  }
  startBillboardLoop();

  // ---------------- Relógio Digital ----------------
  function clock() {
    const now = new Date();
    const parts = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }).split(':');
    if (els.clock) els.clock.innerHTML = `<span>${parts[0]}</span><i>:</i><span>${parts[1]}</span>`;
    if (els.clockDate) els.clockDate.textContent = now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' });
  }
  setInterval(clock, 1000);
  clock();

  // ---------------- Vídeo Ambiente do Estádio ----------------
  function syncAmbient() {
    const video = els.screen ? els.screen.querySelector('.ambient-video') : null;
    if (!video) return;
    if (reduced || document.hidden) {
      video.pause();
      video.hidden = true;
      return;
    }
    video.muted = true;
    if (!video.getAttribute('src')) video.src = video.dataset.src;
    video.onplaying = () => { video.hidden = false; };
    video.onerror = () => { video.hidden = true; };
    const pending = video.play();
    if (pending?.catch) pending.catch(() => { video.hidden = true; });
  }

  // ---------------- Event Listeners Globais ----------------
  document.addEventListener('click', async e => {
    const b = e.target.closest('button, [data-act]');
    if (!b) return;

    // Ações de categorias
    if (b.dataset.catId) {
      const catId = b.dataset.catId;
      const catName = b.dataset.catName;
      state.categoryId = catId;
      state.category = catName;

      showOverlay("Carregando catálogo…", catName);
      if (state.kind === 'movie') {
        if (!vodCache[catId]) {
          vodCache[catId] = await fetchVodStreams(session.user, session.pass, catId);
        }
      } else if (state.kind === 'series') {
        if (!seriesCache[catId]) {
          seriesCache[catId] = await fetchSeries(session.user, session.pass, catId);
        }
      }
      hideOverlay();
      go({ view: 'catalog', query: '' });
      return;
    }

    // Ações de itens de catálogo
    if (b.dataset.itemId) {
      const id = b.dataset.itemId;
      const type = b.dataset.itemType;
      showOverlay("Carregando título…", "");
      if (type === 'movie') {
        const item = (vodCache[state.categoryId] || []).find(v => String(v.stream_id) === String(id));
        selectedItem = item;
      } else {
        const item = (seriesCache[state.categoryId] || []).find(s => String(s.series_id) === String(id));
        selectedItem = item;
      }
      hideOverlay();
      go({ view: 'detail', title: id });
      return;
    }

    // Ações de temporadas
    if (b.dataset.seasonNum) {
      state.season = Number(b.dataset.seasonNum);
      go({ view: 'episodes' });
      return;
    }

    // Ações de episódios
    if (b.dataset.episodeId) {
      const epId = b.dataset.episodeId;
      const epTitle = b.dataset.episodeTitle;
      const epExt = b.dataset.episodeExt || 'mp4';
      const user = session ? session.user : '';
      const pass = session ? session.pass : '';
      const url = apiUrl(`/series/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${epId}.${epExt}`);
      playVodMedia(url, epTitle);
      return;
    }

    // Ações de canais de TV
    if (b.dataset.channelId) {
      const id = b.dataset.channelId;
      const name = b.dataset.channelName;
      playStream(id, name);
      return;
    }

    // Ações por data-act
    const act = b.dataset.act || b.dataset.action;
    switch (act) {
      case 'back':
        back();
        break;
      case 'home':
        go({ view: 'home' });
        break;
      case 'live':
        go({ view: 'live', query: '' });
        break;
      case 'sports':
        go({ view: 'sports', query: '' });
        break;
      case 'movie':
      case 'series':
        showOverlay("Carregando categorias…", "");
        if (act === 'movie' && !vodCategories.length) {
          vodCategories = await fetchVodCategories(session.user, session.pass);
        } else if (act === 'series' && !seriesCategories.length) {
          seriesCategories = await fetchSeriesCategories(session.user, session.pass);
        }
        hideOverlay();
        go({ view: 'categories', kind: act, query: '' });
        break;
      case 'favorites':
        go({ view: 'favorites', query: '' });
        break;
      case 'next':
        state.page++;
        draw();
        break;
      case 'prev':
        state.page = Math.max(0, state.page - 1);
        draw();
        break;
      case 'load-seasons':
        showOverlay("Carregando temporadas…", "");
        if (selectedItem && selectedItem.series_id && !seriesInfoCache[selectedItem.series_id]) {
          const info = await fetchSeriesInfo(session.user, session.pass, selectedItem.series_id);
          selectedItem.seasons = info.seasons || [];
          selectedItem.episodes = info.episodes || {};
          seriesInfoCache[selectedItem.series_id] = info;
        }
        hideOverlay();
        go({ view: 'seasons' });
        break;
      case 'play-movie':
        if (selectedItem) {
          const user = session ? session.user : '';
          const pass = session ? session.pass : '';
          const ext = selectedItem.container_extension || 'mp4';
          const url = apiUrl(`/movie/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${selectedItem.stream_id}.${ext}`);
          playVodMedia(url, selectedItem.name);
        }
        break;
      case 'account':
        go({ view: 'account' });
        break;
      case 'epg':
        go({ view: 'epg' });
        break;
      case 'back-to-player':
        if (els.playerLayer) els.playerLayer.classList.remove("hidden");
        break;
      case 'favorite':
        toggleActiveFavorite();
        break;
      case 'motion':
        reduced = !reduced;
        document.body.classList.toggle('motion-off', reduced);
        b.textContent = reduced ? 'Ativar movimento' : 'Pausar movimento';
        syncAmbient();
        break;
    }
  });

  // Eventos do Player Persistente
  if (els.btnPlayerBack) {
    els.btnPlayerBack.addEventListener("click", () => {
      closePlayer();
    });
  }
  if (els.btnPlayerFav) {
    els.btnPlayerFav.addEventListener("click", () => {
      toggleActiveFavorite();
    });
  }
  if (els.btnPlayerEpg) {
    els.btnPlayerEpg.addEventListener("click", () => {
      if (els.playerLayer) els.playerLayer.classList.add("hidden");
      go({ view: 'epg' });
    });
  }
  if (els.btnZoom) {
    els.btnZoom.addEventListener("click", toggleZoom);
  }
  if (els.btnFullscreen) {
    els.btnFullscreen.addEventListener("click", toggleFullscreen);
  }

  // Duplo toque / clique no vídeo para Zoom
  let lastTouchEndTime = 0;
  if (els.playerWrap) {
    els.playerWrap.addEventListener("touchend", e => {
      if (e.target.closest("button, a")) return;
      const now = Date.now();
      if (now - lastTouchEndTime < 350) {
        e.preventDefault();
        toggleZoom();
        lastTouchEndTime = 0;
        return;
      }
      lastTouchEndTime = now;
    }, { passive: false });

    els.playerWrap.addEventListener("dblclick", e => {
      if (e.target.closest("button, a")) return;
      e.preventDefault();
      toggleZoom();
    });
  }

  // Campo de Busca Dinâmica
  document.addEventListener('input', e => {
    if (e.target.id === 'tvSearch') {
      state.query = e.target.value;
      state.page = 0;
      draw(true);
    }
  });

  // Controle Remoto Smart TV (D-Pad) & Teclado
  document.addEventListener('keydown', e => {
    if (['Escape', 'BrowserBack', 'GoBack'].includes(e.key) || [10009, 461].includes(e.keyCode)) {
      e.preventDefault();
      if (els.playerLayer && !els.playerLayer.classList.contains("hidden")) {
        closePlayer();
      } else {
        back();
      }
      return;
    }

    if (!e.key.startsWith('Arrow') || ['INPUT', 'VIDEO'].includes(e.target.tagName)) return;

    const elsList = [...document.querySelectorAll('button:not(:disabled), a, input')].filter(x => x.getClientRects().length);
    const active = document.activeElement;
    if (!elsList.includes(active)) {
      elsList[0]?.focus();
      return;
    }

    const a = active.getBoundingClientRect();
    const vertical = ['ArrowUp', 'ArrowDown'].includes(e.key);
    const sign = ['ArrowDown', 'ArrowRight'].includes(e.key) ? 1 : -1;
    let best, score = Infinity;

    for (const el of elsList) {
      if (el === active) continue;
      const b = el.getBoundingClientRect();
      const dx = b.x + b.width / 2 - a.x - a.width / 2;
      const dy = b.y + b.height / 2 - a.y - a.height / 2;
      const p = (vertical ? dy : dx) * sign;
      const s = Math.abs(vertical ? dx : dy);
      if (p > 2 && p + s * 3 < score) {
        score = p + s * 3;
        best = el;
      }
    }

    e.preventDefault();
    best?.focus();
  });

  // ---------------- Proxy e API Helpers ----------------
  function toProxied(absoluteOrPath) {
    if (!absoluteOrPath) return absoluteOrPath;
    try {
      const u = new URL(absoluteOrPath, window.location.origin);
      if (u.origin === window.location.origin) return u.href;
      return window.location.origin + PROXY_BASE + u.pathname + u.search;
    } catch (e) {
      return absoluteOrPath;
    }
  }

  function apiUrl(path) {
    return PROXY_BASE + path;
  }

  async function xtreamLogin(user, pass) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status} ao autenticar`);
    const data = await res.json();
    const info = data.user_info || {};
    if (String(info.auth) !== "1" || (info.status && info.status !== "Active")) {
      throw new Error(info.message || "Usuário ou senha inválidos, ou conta expirada.");
    }
    return data;
  }

  async function fetchLiveStreams(user, pass) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_live_streams`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error("Falha ao carregar lista de canais.");
    return res.json();
  }

  async function fetchCategories(user, pass) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_live_categories`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  }

  async function fetchVodCategories(user, pass) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_vod_categories`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  }

  async function fetchVodStreams(user, pass, catId) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_vod_streams&category_id=${encodeURIComponent(catId)}`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  }

  async function fetchSeriesCategories(user, pass) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_series_categories`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  }

  async function fetchSeries(user, pass, catId) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_series&category_id=${encodeURIComponent(catId)}`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  }

  async function fetchSeriesInfo(user, pass, seriesId) {
    const url = apiUrl(`/player_api.php?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&action=get_series_info&series_id=${encodeURIComponent(seriesId)}`);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return {};
    return res.json();
  }

  // ---------------- Sessão e Autenticação ----------------
  async function startSession(user, pass) {
    if (els.loginGate) els.loginGate.classList.add("hidden");
    if (els.appShell) els.appShell.classList.remove("hidden");

    session = { user, pass };
    localStorage.setItem("nexus_play_session", JSON.stringify(session));

    if (els.footUser) els.footUser.textContent = `NEXUS PLATFORM • CONTA: ${user.toUpperCase()} (ATIVA)`;

    // Carrega em segundo plano canais e categorias reais
    try {
      showOverlay("Conectando…", "Carregando grade oficial de canais.");
      const [streams, cats] = await Promise.all([
        fetchLiveStreams(user, pass),
        fetchCategories(user, pass)
      ]);
      allStreams = streams;
      allCategories = cats;
      hideOverlay();
      draw();
    } catch (err) {
      hideOverlay();
      notice("Conectado! Alguns dados ainda estão sincronizando.");
      draw();
    }
  }

  function logout() {
    destroyPlayer();
    localStorage.removeItem("nexus_play_session");
    localStorage.removeItem("nexus_tv_pin");
    session = null;
    activeStreamId = null;

    if (els.playerLayer) els.playerLayer.classList.add("hidden");
    if (els.appShell) els.appShell.classList.add("hidden");
    if (els.loginGate) els.loginGate.classList.remove("hidden");

    initQrCode();
  }

  if (els.btnLogin) {
    els.btnLogin.addEventListener("click", async () => {
      const u = (els.inUser.value || "").trim();
      const p = (els.inPass.value || "").trim();
      if (!u || !p) {
        if (els.loginErr) els.loginErr.textContent = "Informe usuário e senha.";
        return;
      }
      els.btnLogin.disabled = true;
      if (els.loginErr) els.loginErr.textContent = "Conectando…";
      try {
        await xtreamLogin(u, p);
        if (els.loginErr) els.loginErr.textContent = "";
        startSession(u, p);
      } catch (err) {
        if (els.loginErr) els.loginErr.textContent = err.message || "Erro ao conectar.";
      } finally {
        els.btnLogin.disabled = false;
      }
    });
  }

  if (els.btnLogout) {
    els.btnLogout.addEventListener("click", logout);
  }

  [els.inUser, els.inPass].forEach(inp => {
    if (inp) {
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter" && els.btnLogin) els.btnLogin.click();
      });
    }
  });

  const btnTogglePass = document.getElementById("btnTogglePass");
  if (btnTogglePass) {
    btnTogglePass.addEventListener("click", () => {
      const isPass = els.inPass.type === "password";
      els.inPass.type = isPass ? "text" : "password";
      const iconEye = btnTogglePass.querySelector(".icon-eye");
      const iconEyeOff = btnTogglePass.querySelector(".icon-eye-off");
      if (iconEye && iconEyeOff) {
        iconEye.style.display = isPass ? "block" : "none";
        iconEyeOff.style.display = isPass ? "none" : "block";
      }
    });
  }

  // ---------------- Pareamento QR Code Inteligente ----------------
  async function initQrCode() {
    const pinEl = document.getElementById("qrPinCode");
    const imgEl = document.getElementById("qrCodeImg");
    if (!pinEl || !imgEl) return;

    try {
      const res = await fetch(`${PAIR_BASE}/generate`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      pinEl.textContent = data.pin;

      const pairUrl = `${window.location.origin}${window.location.pathname}?pair=${data.pin}`;
      if (window.QRCode) {
        imgEl.style.display = "none";
        let inlineContainer = document.getElementById("qrInlineTarget");
        if (!inlineContainer) {
          inlineContainer = document.createElement("div");
          inlineContainer.id = "qrInlineTarget";
          imgEl.parentNode.appendChild(inlineContainer);
        }
        inlineContainer.innerHTML = "";
        new window.QRCode(inlineContainer, {
          text: pairUrl,
          width: 80,
          height: 80,
          colorDark: "#000000",
          colorLight: "#ffffff",
          correctLevel: window.QRCode.CorrectLevel.M
        });
      }

      startPairPolling(data.pin);
    } catch (e) {
      console.warn("QR code offline:", e);
    }
  }

  function startPairPolling(pin) {
    if (pairPollTimer) clearInterval(pairPollTimer);
    pairPollTimer = setInterval(async () => {
      try {
        const res = await fetch(`${PAIR_BASE}/status?pin=${encodeURIComponent(pin)}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "paired" && data.user && data.pass) {
          clearInterval(pairPollTimer);
          fetch(`${PAIR_BASE}/consume`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pin })
          }).catch(() => {});
          startSession(data.user, data.pass);
        }
      } catch (e) {}
    }, 400);
  }

  // ---------------- Boot da Aplicação ----------------
  async function boot() {
    const urlParams = new URLSearchParams(window.location.search);
    const pairParam = urlParams.get("pair");

    // Sessão prévia salva
    try {
      const saved = localStorage.getItem("nexus_play_session");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.user && parsed.pass) {
          startSession(parsed.user, parsed.pass);
          return;
        }
      }
    } catch (e) {}

    // Inicia QR code se estiver no login
    initQrCode();
  }

  boot();
})();
