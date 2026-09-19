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
    liveCat: 'all', // categoria ativa na Interface TV Premium de 3 Colunas ('all' | 'fav' | 'sports' | <category_id>)
    page: 0,
    title: null,
    season: 1,
    query: ''
  };
  let stack = [];
  let focusMemory = '';
  let transitionBack = false;

  // Foco atual da coluna de canais (usado para popular a coluna de EPG Detalhado
  // da Interface TV Premium de 3 Colunas — atualizado por mouse, foco e D-pad)
  let tv3FocusId = null;
  let tv3FocusName = '';
  let tv3FocusIcon = '';
  const TV3_PAGE_SIZE = 40;

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

  // 1. HOME (Bento Cinematográfico com Banners e Vídeos Rotativos em Loop)
  const HERO_THEMES = [
    {
      img: "assets/banners/futebol.webp",
      vid: "assets/banners/futebol-1080p.mp4",
      title: "A noite.<br>O jogo.<br>O seu play.",
      sub: "A emoção do esporte ao vivo com transmissão em Full HD 60 FPS."
    },
    {
      img: "assets/banners/cinema.webp",
      vid: "assets/banners/cinema-1080p.mp4",
      title: "Grandes histórias.<br>Cinema em casa.<br>Sem limites.",
      sub: "Mais de 20.000 filmes e temporadas completas dos maiores estúdios."
    },
    {
      img: "assets/banners/basquete.webp",
      vid: "assets/banners/basquete-1080p.mp4",
      title: "A decisão.<br>Cada cesta.<br>Em tempo real.",
      sub: "As maiores ligas esportivas mundiais com estabilidade total."
    },
    {
      img: "assets/banners/combate.webp",
      vid: "assets/banners/combate-1080p.mp4",
      title: "O octógono.<br>A disputa.<br>Ao vivo.",
      sub: "Eventos mundiais de luta e grandes combates direto na sua tela."
    }
  ];

  function homeView() {
    const liveCount = allStreams.length || "1.790+";
    const theme = HERO_THEMES[Math.floor(Math.random() * HERO_THEMES.length)];
    return `<section class="tv-home">
      <img class="scenery" src="${theme.img}" alt="">
      <video class="ambient-video" muted loop playsinline preload="auto" data-src="${theme.vid}" aria-hidden="true" tabindex="-1"></video>
      <div class="stadium-lights" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="home-copy">
        <span class="eyebrow">Nexus / O seu lugar na primeira fila</span>
        <h1>${theme.title}</h1>
        <p>${theme.sub}</p>
        <button class="primary" data-act="live" data-key="home-live">${icon('play')} Abrir TV ao vivo</button>
      </div>
      <div class="destinations">
        <button class="destination" data-act="live" data-key="home-live-dest">
          <img src="assets/banners/futebol.webp" alt="">
          <span>01</span>
          <strong>TV ao vivo</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="sports" data-key="home-sports">
          <img src="assets/banners/basquete.webp" alt="">
          <span>02</span>
          <strong>Jogos do Dia</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="movie" data-key="home-movies">
          <img src="assets/banners/cinema.webp" alt="">
          <span>03</span>
          <strong>Filmes</strong>
          ${icon('next')}
        </button>
        <button class="destination" data-act="series" data-key="home-series">
          <img src="assets/banners/combate.webp" alt="">
          <span>04</span>
          <strong>Séries</strong>
          ${icon('next')}
        </button>
      </div>
    </section>`;
  }

  // ---------------- Marcas e Estúdios de Streaming ----------------
  const BRAND_LOGOS = {
    'NETFLIX': '<span style="color:#E50914;font-family:\'Space Grotesk\',sans-serif;font-weight:900;font-size:22px;letter-spacing:1.5px;">NETFLIX</span>',
    'AMAZON PRIME VIDEO': '<svg viewBox="0 0 110 30" style="height:20px;"><text x="2" y="22" fill="#00A8E1" font-family="\'Space Grotesk\',sans-serif" font-weight="900" font-size="20">prime</text><text x="64" y="22" fill="#fff" font-family="\'Space Grotesk\',sans-serif" font-weight="500" font-size="16">video</text></svg>',
    'DISNEY+': '<svg viewBox="0 0 100 30" style="height:22px;"><text x="10" y="22" fill="#fff" font-family="\'Space Grotesk\',sans-serif" font-weight="900" font-size="22">Disney<tspan fill="#0063e5">+</tspan></text></svg>',
    'HBO MAX': '<svg viewBox="0 0 100 30" style="height:22px;"><text x="12" y="22" fill="#fff" font-family="\'Space Grotesk\',sans-serif" font-weight="900" font-size="22" letter-spacing="2">MAX</text></svg>',
    'APPLETV+': '<svg viewBox="0 0 100 30" style="height:20px;"><text x="15" y="22" fill="#fff" font-family="\'Space Grotesk\',sans-serif" font-weight="700" font-size="20">tv+</text></svg>',
    'GLOBOPLAY': '<svg viewBox="0 0 110 30" style="height:20px;"><circle cx="14" cy="14" r="8" fill="#FB0" stroke="#FF0043" stroke-width="3"/><text x="30" y="20" fill="#fff" font-family="\'Space Grotesk\',sans-serif" font-weight="700" font-size="16">globoplay</text></svg>',
    'PARAMOUNT+': '<svg viewBox="0 0 120 30" style="height:20px;"><text x="5" y="21" fill="#0064FF" font-family="\'Space Grotesk\',sans-serif" font-weight="900" font-size="18">Paramount+</text></svg>'
  };

  const GENRE_BACKDROPS = [
    "assets/cards/01-lancamentos-2026.webp",
    "assets/cards/02-top-50.webp",
    "assets/cards/03-sucessos-do-cinema.webp",
    "assets/cards/04-acao-adrenalina.webp",
    "assets/cards/05-comedia.webp",
    "assets/cards/06-drama-emocao.webp",
    "assets/cards/07-terror-horror.webp",
    "assets/cards/08-suspense-misterio.webp",
    "assets/cards/09-ficcao-fantasia.webp",
    "assets/cards/10-animacao-familia.webp",
    "assets/cards/11-cinema-nacional.webp",
    "assets/cards/12-documentarios.webp",
    "assets/cards/13-crime-investigacao.webp",
    "assets/cards/14-guerra-historia.webp",
    "assets/cards/15-animes-manga.webp",
    "assets/cards/16-faroeste-western.webp"
  ];

  const GENRE_CARD_IMAGES = {
    'LANCAMENTOS': 'assets/cards/01-lancamentos-2026.webp',
    'TOP 50 FILMES 2026': 'assets/cards/02-top-50.webp',
    'CINEMA': 'assets/cards/03-sucessos-do-cinema.webp',
    'ACAO': 'assets/cards/04-acao-adrenalina.webp',
    'COMEDIA': 'assets/cards/05-comedia.webp',
    'DRAMA': 'assets/cards/06-drama-emocao.webp',
    'TERROR': 'assets/cards/07-terror-horror.webp',
    'SUSPENSE': 'assets/cards/08-suspense-misterio.webp',
    'THRILLER': 'assets/cards/08-suspense-misterio.webp',
    'FICCAO/FANTASIA': 'assets/cards/09-ficcao-fantasia.webp',
    'FICCAO CIENTIFICA': 'assets/cards/09-ficcao-fantasia.webp',
    'FANTASIA': 'assets/cards/09-ficcao-fantasia.webp',
    'ANIMACAO/INFANTIL': 'assets/cards/10-animacao-familia.webp',
    'ANIMACAO': 'assets/cards/10-animacao-familia.webp',
    'FAMILIA': 'assets/cards/10-animacao-familia.webp',
    'DESENHOS': 'assets/cards/10-animacao-familia.webp',
    'NACIONAIS': 'assets/cards/11-cinema-nacional.webp',
    'DOCUMENTARIOS': 'assets/cards/12-documentarios.webp',
    'CRIME': 'assets/cards/13-crime-investigacao.webp',
    'GUERRA': 'assets/cards/14-guerra-historia.webp',
    'ANIMES': 'assets/cards/15-animes-manga.webp',
    'FAROESTE': 'assets/cards/16-faroeste-western.webp',
    'LEGENDADOS': 'assets/cards/03-sucessos-do-cinema.webp',
    'UHD 4K': 'assets/cards/01-lancamentos-2026.webp',
    'RELIGIOSOS': 'assets/cards/06-drama-emocao.webp',
    'ROMANCE': 'assets/cards/06-drama-emocao.webp'
  };

  function getGenreImage(rawName, index) {
    if (!rawName) return GENRE_BACKDROPS[index % GENRE_BACKDROPS.length];
    let s = String(rawName).trim().replace(/^(FILMES|SERIES)\s*\|\s*/i, '').toUpperCase();
    return GENRE_CARD_IMAGES[s] || GENRE_BACKDROPS[index % GENRE_BACKDROPS.length];
  }

  const ADULT_REGEX = /(XXX|18\+|ADULTO|PORNO|HENTAI|PRIVE|SEXTREME)/i;
  let adultUnlocked = sessionStorage.getItem("nexus_adult_unlocked") === "true";
  const DEFAULT_ADULT_PIN = "0000";

  function formatVodCatName(raw) {
    if (!raw) return 'Catálogo';
    let s = String(raw).trim();
    s = s.replace(/^(FILMES|SERIES)\s*\|\s*/i, '');
    const MAP = {
      'LANCAMENTOS': 'Lançamentos 2026',
      'TOP 50 FILMES 2026': 'Top 50 • Mais Assistidos',
      'CINEMA': 'Sucessos do Cinema',
      'ACAO': 'Ação & Adrenalina',
      'COMEDIA': 'Comédia',
      'DRAMA': 'Drama & Emoção',
      'LEGENDADOS': 'Filmes Legendados',
      'TERROR': 'Terror & Horror',
      'SUSPENSE': 'Suspense & Mistério',
      'ANIMACAO/INFANTIL': 'Animação & Família',
      'NACIONAIS': 'Cinema Nacional',
      'DOCUMENTARIOS': 'Documentários',
      'FICCAO/FANTASIA': 'Ficção & Fantasia',
      'ROMANCE': 'Romance',
      'ANIMES': 'Animes & Mangá',
      'FAROESTE': 'Faroeste & Western',
      'CRIME': 'Crime & Investigação',
      'GUERRA': 'Guerra & História',
      'RELIGIOSOS': 'Fé & Religiosos',
      'NETFLIX': 'Netflix Originais',
      'AMAZON PRIME VIDEO': 'Prime Video',
      'GLOBOPLAY': 'Globoplay',
      'HBO MAX': 'Max / HBO',
      'DISNEY+': 'Disney+',
      'APPLETV+': 'Apple TV+',
      'PARAMOUNT+': 'Paramount+',
      'STAR+': 'Star+',
      'DISCOVERY+': 'Discovery+'
    };
    const upper = s.toUpperCase().trim();
    return MAP[upper] || s;
  }

  // 2. CATEGORIAS DE FILMES E SÉRIES — PADRÃO REDPLAY / NETFLIX PREMIUM
  function categoriesView() {
    let cats = [];
    let title = "Catálogo";
    let sub = "Streaming Premium sob demanda";

    if (state.kind === 'movie') {
      cats = vodCategories.length ? vodCategories : [{ category_id: "557", category_name: "Lançamentos Cinema" }];
      title = "Cine Nexus";
      sub = "Mais de 20.000 filmes em Full HD e Ultra HD";
    } else if (state.kind === 'series') {
      cats = seriesCategories.length ? seriesCategories : [{ category_id: "7837", category_name: "Séries em Destaque" }];
      title = "Séries Nexus";
      sub = "Temporadas completas dos maiores estúdios do mundo";
    }

    // Deduplicação estrita de estúdios (apenas 1 botão por marca)
    const seenBrands = new Set();
    const brandCats = [];
    cats.forEach(c => {
      const u = (c.category_name || '').toUpperCase();
      const brandKey = Object.keys(BRAND_LOGOS).find(b => u.includes(b));
      if (brandKey && !seenBrands.has(brandKey)) {
        seenBrands.add(brandKey);
        brandCats.push({ ...c, brandKey });
      }
    });

    const otherCats = cats.filter(c => {
      const u = (c.category_name || '').toUpperCase();
      return !Object.keys(BRAND_LOGOS).some(b => u.includes(b));
    });

    let brandsHtml = '';
    if (brandCats.length > 0) {
      brandsHtml = `
      <div class="brand-hub-section">
        <div class="brand-hub-title">Estúdios & Plataformas Integradas</div>
        <div class="brand-hub-grid">
          ${brandCats.map(c => {
            const logoSvg = BRAND_LOGOS[c.brandKey] || `<strong>${safe(formatVodCatName(c.category_name))}</strong>`;
            return `
            <button class="brand-hub-card" data-cat-id="${c.category_id}" data-cat-name="${safe(formatVodCatName(c.category_name))}" data-key="cat-${c.category_id}">
              ${logoSvg}
            </button>`;
          }).join('')}
        </div>
      </div>`;
    }

    const bgBanner = state.kind === 'series' ? 'assets/banners/combate.webp' : 'assets/banners/cinema.webp';

    return `<div class="tv-vod-shell">
      <img class="tv3-bg" src="${bgBanner}" alt="">
      <div class="tv3-scrim"></div>
      <div class="tv-vod-content">
        ${topBar(title, sub)}
        ${brandsHtml}
        <div class="brand-hub-title" style="margin-top:12px;">Gêneros & Coleções em Alta</div>
        <div class="genre-cards-grid">
          ${otherCats.map((c, i) => {
            const isAdult = ADULT_REGEX.test(c.category_name);
            const clean = isAdult ? 'Adultos (+18)' : formatVodCatName(c.category_name);
            const bgImg = isAdult ? 'assets/banners/combate.webp' : getGenreImage(c.category_name, i);
            const badgeText = isAdult ? (adultUnlocked ? 'DESBLOQUEADO' : '🔒 PIN REQUERIDO') : 'FHD • 1080P';
            const badgeStyle = isAdult ? 'color:#ff5555;border-color:#ff555555;background:#ff555518;' : '';
            return `
            <button class="genre-card ${isAdult && !adultUnlocked ? 'is-adult-locked' : ''}" data-cat-id="${c.category_id}" data-cat-name="${safe(clean)}" data-is-adult="${isAdult}" data-key="cat-${c.category_id}">
              <img class="genre-card-bg" src="${bgImg}" alt="" loading="lazy">
              <div class="genre-card-scrim"></div>
              <div class="genre-card-content">
                <div class="genre-card-top">
                  <span class="genre-card-badge" style="${badgeStyle}">${badgeText}</span>
                  <span class="genre-card-num">${String(i + 1).padStart(2, '0')}</span>
                </div>
                <div>
                  <strong class="genre-card-title">${safe(clean)}</strong>
                  <span class="genre-card-cta">${isAdult && !adultUnlocked ? 'Desbloquear com PIN' : 'Explorar títulos'} ${icon('next')}</span>
                </div>
              </div>
            </button>`;
          }).join('')}
        </div>
      </div>
    </div>`;
  }

  // 3. CATÁLOGO DE PÔSTERES COM ROLAGEM HORIZONTAL E SETAS LATERAIS (Padrão RedPlay / Netflix)
  function catalogView() {
    const list = getCatalogItems();
    const typeLabel = state.kind === 'series' ? 'Séries' : 'Filmes';
    const catName = formatVodCatName(state.category || 'Catálogo');

    const firstItem = list[0] || {};
    const firstTitle = cleanTitle(firstItem.name || 'Selecione um título');
    const firstPlot = firstItem.plot || "Navegue pelo carrossel ou passe o cursor sobre qualquer pôster para ver detalhes completos e sinopse.";
    const firstYear = firstItem.year || firstItem.rating || "2026";
    const firstRate = firstItem.rating || "8.5";
    const firstId = firstItem.stream_id || firstItem.series_id || "";

    const bgBanner = state.kind === 'series' ? 'assets/banners/combate.webp' : 'assets/banners/cinema.webp';

    return `<div class="tv-vod-shell">
      <img class="tv3-bg" src="${bgBanner}" alt="">
      <div class="tv3-scrim"></div>
      <div class="tv-vod-content">
        ${topBar(catName, `${typeLabel} / ${list.length} títulos disponíveis`)}
        <div class="tv-search" style="margin-bottom:12px;">
          <input id="tvSearch" type="search" value="${safe(state.query)}" placeholder="Buscar por título, ator ou gênero…" aria-label="Buscar neste catálogo">
          <button data-act="back" style="padding:8px 16px;border-radius:8px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#fff;cursor:pointer;">${icon('back')} Voltar</button>
        </div>

        <div class="rail-wrapper">
          <button class="rail-nav-btn rail-prev" data-rail-scroll="-1" aria-label="Deslizar para a esquerda">‹</button>
          <div class="rail-track" id="vodTrack">
            ${list.map(t => {
              const cover = t.stream_icon || t.cover || "design/posters/dune.webp";
              const yr = t.year || t.rating || "HD";
              const title = cleanTitle(t.name || 'Título');
              const plot = t.plot || 'Assista a esta superprodução em alta definição na Nexus PlayTV.';
              return `
              <button class="rail-item" data-item-id="${t.stream_id || t.series_id}" data-item-type="${state.kind}"
                data-vod-title="${safe(title)}" data-vod-plot="${safe(plot)}" data-vod-year="${safe(String(yr))}" data-vod-rate="${safe(String(t.rating || '8.5'))}"
                data-key="item-${t.stream_id || t.series_id}">
                <img class="rail-item-cover" src="${cover}" loading="lazy" onerror="this.onerror=null;this.src='design/posters/dune.webp';" alt="">
                <div class="rail-item-info">
                  <strong class="rail-item-title">${safe(title)}</strong>
                  <div class="rail-item-meta">
                    <span>${safe(String(yr))}</span>
                    <span style="color:#b7ff3c;">★ ${t.rating || '8.5'}</span>
                  </div>
                </div>
              </button>`;
            }).join('') || '<p class="empty">Nenhum título encontrado nesta categoria.</p>'}
          </div>
          <button class="rail-nav-btn rail-next" data-rail-scroll="1" aria-label="Deslizar para a direita">›</button>
        </div>

        <!-- Painel OSD de Detalhes Dinâmico no Rodapé (Exibe título completo e sinopse ao navegar) -->
        <div class="vod-detail-bar" id="vodDetailBar">
          <div class="vod-detail-info">
            <span class="vod-detail-badge" id="vodDetailBadge">FHD • 1080P</span>
            <h3 class="vod-detail-title" id="vodDetailTitle">${safe(firstTitle)}</h3>
            <div class="vod-detail-meta" id="vodDetailMeta">
              <span id="vodDetailYear">${safe(String(firstYear))}</span> • <span>${safe(catName)}</span> • <span id="vodDetailRating" style="color:#b7ff3c;">★ ${safe(String(firstRate))}</span>
            </div>
            <p class="vod-detail-plot" id="vodDetailPlot">${safe(firstPlot)}</p>
          </div>
          <div class="vod-detail-actions">
            <button class="vod-detail-play" id="vodDetailPlayBtn" data-item-id="${firstId}" data-item-type="${state.kind}">▶ Assistir Agora</button>
          </div>
        </div>
      </div>
    </div>`;
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
    const plot = t.plot || "Assista a esta superprodução em alta definição na Nexus PlayTV com streaming contínuo sem travamentos.";
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
  // ---------------- Interface TV Premium de 3 Colunas ----------------
  // Categorias (esquerda) | Canais com logos oficiais (centro) | EPG Detalhado (direita)
  // Inspirada em BTV 13 / RedPlay TV Box e Claro Box Mosaico.

  function tv3SportsFilter(c) {
    const n = String(c.name || '').toLowerCase();
    const catN = String(c.category_name || '').toLowerCase();
    return n.includes(' x ') || n.includes(' vs ') || /\b\d{1,2}:\d{2}\b/.test(n) || catN.includes('esporte') || catN.includes('premiere') || catN.includes('sportv') || catN.includes('espn');
  }

  function cleanTitle(s) {
    if (!s) return '';
    return String(s)
      .replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{27BF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[⚽🤠📺🎬🍿⭐🔥🏆👑🎯]/gu, '')
      .replace(/^[\|\-\s]+|[\|\-\s]+$/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function tv3Categories() {
    const pseudo = [
      { id: 'all', name: 'TODOS' },
      { id: 'fav', name: 'FAVORITOS' },
      { id: 'sports', name: 'ESPORTE' }
    ];
    const seen = new Set();
    const real = allCategories.filter(c => {
      if (!c || c.category_id == null || seen.has(String(c.category_id))) return false;
      const has = allStreams.some(s => String(s.category_id) === String(c.category_id));
      if (has) seen.add(String(c.category_id));
      return has;
    }).map(c => ({ id: String(c.category_id), name: cleanTitle(c.category_name) || 'Categoria' }));
    return pseudo.concat(real);
  }

  function tv3FilterList() {
    let list = allStreams;
    const cat = state.liveCat || 'all';
    if (cat === 'fav') list = list.filter(c => savedFavs.includes(String(c.stream_id)));
    else if (cat === 'sports') list = list.filter(tv3SportsFilter);
    else if (cat !== 'all') list = list.filter(c => String(c.category_id) === String(cat));

    if (state.query) {
      const q = state.query.toLowerCase();
      list = list.filter(c => (c.name || '').toLowerCase().includes(q));
    }
    return list;
  }

  function tv3Paging(total) {
    const pages = Math.max(1, Math.ceil(total / TV3_PAGE_SIZE));
    if (pages <= 1) return '';
    return `<div class="paging tv3-paging">
      <button data-act="prev" ${state.page === 0 ? 'disabled' : ''} aria-label="Página anterior">${icon('back')}</button>
      <span>${state.page + 1} / ${pages}</span>
      <button data-act="next" ${state.page >= pages - 1 ? 'disabled' : ''} aria-label="Próxima página">${icon('next')}</button>
    </div>`;
  }

  // EPG Detalhado (coluna 3) — atualizado ao focar/apontar para um canal na coluna 2,
  // sem redesenhar a tela inteira (preserva rolagem e foco do D-pad).
  function renderTv3EpgPanel(chan) {
    if (!chan) {
      return `<div class="tv3-epg-empty"><p>Aponte para um canal para ver a programação.</p></div>`;
    }
    const name = chan.name || 'Canal';
    const logo = chan.stream_icon ? toProxied(chan.stream_icon) : '';
    const cacheKey = `${name}|${chan.stream_icon || ''}`;
    const epg = epgCache[cacheKey];

    const head = `<div class="tv3-epg-head">
      ${logo ? `<img src="${logo}" alt="" onerror="this.remove()">` : `<span class="tv3-epg-mono">${safe((name || '?').trim().charAt(0).toUpperCase())}</span>`}
      <div><span class="tv3-epg-live">● AO VIVO</span><h2>${safe(name)}</h2></div>
    </div>`;

    if (!epg) {
      fetchEpgData(name, chan.stream_icon || '').then(() => {
        if (String(tv3FocusId) === String(chan.stream_id)) {
          const panel = document.getElementById('tv3EpgPanel');
          if (panel) panel.innerHTML = renderTv3EpgPanel(chan);
        }
      });
      return `${head}
      <div class="tv3-epg-loading">
        <div class="spinner"></div>
        <p>Consultando programação em tempo real…</p>
      </div>`;
    }

    const cur = epg.current || {};
    const upcoming = epg.upcoming || [];
    return `${head}
    <div class="tv3-epg-now">
      <div class="tv3-epg-time">${safe(cur.start || '--:--')} – ${safe(cur.stop || '--:--')}</div>
      <h3>${safe(cur.title || 'Transmissão Oficial Nexus')}</h3>
      <p>${safe(cur.desc || 'Assista em alta definição na Nexus PlayTV.')}</p>
      <div class="tv3-epg-bar"><span style="width:${Number(cur.progress) || 0}%"></span></div>
    </div>
    <div class="tv3-epg-next">
      <span class="tv3-epg-label">A seguir na programação</span>
      ${upcoming.slice(0, 5).map(item => `
        <div class="tv3-epg-item">
          <span class="tv3-epg-item-time">${safe(item.start || '')}</span>
          <strong>${safe(item.title || 'Programa')}</strong>
        </div>`).join('') || '<p class="tv3-epg-none">Grade não disponível para este canal.</p>'}
    </div>`;
  }

  // Atualiza o foco de EPG a partir de mouse, toque ou navegação por D-pad/teclado com debounce fluido
  let tv3FocusTimer = null;
  function focusTv3Row(row) {
    if (!row) return;
    const id = row.dataset.channelId;
    if (id == null || String(tv3FocusId) === String(id)) return;
    tv3FocusId = id;
    tv3FocusName = row.dataset.channelName || '';
    tv3FocusIcon = row.dataset.chanIcon || '';

    document.querySelectorAll('.tv3-chan-row.focused').forEach(el => el.classList.remove('focused'));
    row.classList.add('focused');

    if (tv3FocusTimer) clearTimeout(tv3FocusTimer);
    tv3FocusTimer = setTimeout(() => {
      const panel = document.getElementById('tv3EpgPanel');
      if (!panel) return;
      const chan = allStreams.find(c => String(c.stream_id) === String(id)) || { stream_id: id, name: tv3FocusName, stream_icon: tv3FocusIcon };
      panel.innerHTML = renderTv3EpgPanel(chan);
    }, 200);
  }

  function liveView() {
    const cats = tv3Categories();
    const activeCat = state.liveCat || 'all';
    const list = tv3FilterList();
    const paged = list.slice(state.page * TV3_PAGE_SIZE, (state.page + 1) * TV3_PAGE_SIZE);

    // Canal em foco no painel de EPG: mantém o foco anterior se ainda visível na página,
    // senão usa o canal em reprodução, senão o primeiro da lista.
    let focusChan = paged.find(c => String(c.stream_id) === String(tv3FocusId))
      || (activeStreamId != null && paged.find(c => String(c.stream_id) === String(activeStreamId)))
      || paged[0] || null;
    if (focusChan) {
      tv3FocusId = focusChan.stream_id;
      tv3FocusName = focusChan.name;
      tv3FocusIcon = focusChan.stream_icon || '';
    }

    const catLabel = cats.find(c => c.id === activeCat)?.name || 'TV ao Vivo';

    return `
    <div class="tv3-shell" id="tv3Shell">
      <img class="scenery tv3-bg" src="assets/live-cinema.webp" alt="">
      <video class="ambient-video tv3-bg" muted loop playsinline preload="none" data-src="assets/stadium-motion.mp4" aria-hidden="true" tabindex="-1" hidden></video>
      <div class="tv3-scrim" aria-hidden="true"></div>

      <div class="tv3-head">
        <div><span class="eyebrow">Nexus / Grade ao Vivo</span><h1>${safe(catLabel)}</h1></div>
        <button data-act="back">${icon('back')} Voltar</button>
      </div>

      <div class="tv3-body">
        <nav class="tv3-col tv3-col-cats" aria-label="Categorias">
          ${cats.map(c => `
            <button class="tv3-cat-btn ${c.id === activeCat ? 'active' : ''}" data-live-cat="${safe(c.id)}" data-key="tv3cat-${safe(c.id)}">
              ${safe(c.name)}
            </button>
          `).join('')}
        </nav>

        <div class="tv3-col tv3-col-channels">
          <div class="tv3-search">
            <input id="tvSearch" type="search" value="${safe(state.query)}" placeholder="Buscar canal ou partida…" aria-label="Buscar canal">
            <span>${list.length} canais</span>
          </div>
          <div class="tv3-chan-list" role="list">
            ${paged.map((c, i) => {
              const num = c.num ? String(c.num).padStart(3, '0') : String(state.page * TV3_PAGE_SIZE + i + 1).padStart(3, '0');
              const logo = c.stream_icon ? toProxied(c.stream_icon) : '';
              const isFav = savedFavs.includes(String(c.stream_id));
              const isPlaying = activeStreamId != null && String(activeStreamId) === String(c.stream_id);
              const isFocused = String(tv3FocusId) === String(c.stream_id);
              const cleanName = cleanTitle(c.name || 'Canal');
              return `
              <button class="tv3-chan-row ${isPlaying ? 'playing' : ''} ${isFocused ? 'focused' : ''}" role="listitem"
                data-channel-id="${c.stream_id}" data-channel-name="${safe(cleanName)}"
                data-chan-icon="${safe(c.stream_icon || '')}" data-key="chan-${c.stream_id}">
                <span class="tv3-chan-num">${num}</span>
                ${logo
                  ? `<img class="tv3-chan-logo" src="${logo}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" alt="">
                     <span class="tv3-chan-fallback" style="display:none;">${safe(cleanName.charAt(0).toUpperCase())}</span>`
                  : `<span class="tv3-chan-fallback">${safe(cleanName.charAt(0).toUpperCase())}</span>`
                }
                <span class="tv3-chan-meta">
                  <strong>${safe(cleanName)}</strong>
                  <span>${isFav ? '★ Favorito' : 'Canal ao vivo'}</span>
                </span>
                <span class="tv3-chan-star ${isFav ? 'fav-active' : ''}" data-fav-toggle="${c.stream_id}" role="button" title="Favoritar canal">${isFav ? '★' : '☆'}</span>
                ${isPlaying ? '<span class="tv3-live-dot">●</span>' : ''}
              </button>`;
            }).join('') || '<p class="empty">Nenhum canal encontrado nesta categoria.</p>'}
          </div>
          ${tv3Paging(list.length)}
        </div>

        <div class="tv3-col tv3-col-epg" id="tv3EpgPanel">
          ${renderTv3EpgPanel(focusChan)}
        </div>
      </div>
    </div>`;
  }

  // 7. CONTA & STATUS
  function accountView() {
    const u = session ? session.user : "Visitante";
    let expFormatted = "Ativo / Renovação Automática";
    if (session && session.expDate) {
      const ts = Number(session.expDate);
      if (!isNaN(ts) && ts > 0) {
        const d = new Date(ts * 1000);
        expFormatted = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
      }
    }
    return `${topBar('Sua Conta', 'Nexus PlayTV / Status')}
    <div class="empty" style="text-align:left;max-width:600px;margin:20px auto;line-height:2.2;">
      <p><strong>Usuário:</strong> ${u}</p>
      <p><strong>Plano:</strong> <span style="color:#b7ff3c;">● Acesso Premium Ativo</span></p>
      <p><strong>Validade do Plano:</strong> <span style="color:#fff;font-weight:600;">${expFormatted}</span></p>
      <p><strong>Qualidade:</strong> Ultra HD / Full HD 60 FPS</p>
      <p><strong>Dispositivos:</strong> 1 tela conectada</p>
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
    showPlayerControls();

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
          stashInitialSize: 384 * 1024
        });

        tsPlayer.attachMediaElement(video);
        tsPlayer.load();

        let playStarted = false;
        const startPlayback = () => {
          if (playStarted) return;
          playStarted = true;
          hideOverlay();
          video.controls = false;
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
        video.controls = false;
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
      video.controls = false;
      video.play().then(hideOverlay).catch(hideOverlay);
    }
  }

  function playVodMedia(url, name) {
    destroyPlayer();
    if (els.playerLayer) els.playerLayer.classList.remove("hidden");
    showOverlay("Reproduzindo…", name);
    showPlayerControls();

    const video = els.video;
    video.src = toProxied(url);
    video.controls = false;
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
    clearTimeout(playerHideTimer);
    if (els.playerWrap) els.playerWrap.classList.add("active-controls");
  }

  // ---------------- Auto-hide suave da barra inferior do player ----------------
  // A .player-bottom soma 4s após o início da reprodução e reaparece suavemente
  // ao tocar/clicar na tela, mover o mouse ou usar o controle remoto (D-pad/teclado).
  let playerHideTimer = null;
  const PLAYER_HIDE_DELAY = 4000;
  // Só mantém a barra travada quando a navegação veio de controle remoto/teclado
  // (D-pad). Mouse/toque NUNCA travam a barra, senão o foco do botão impede o auto-hide.
  let remoteNavigationActive = false;

  function showPlayerControls(evt) {
    if (!els.playerWrap) return;
    if (evt && evt.type === "keydown") {
      remoteNavigationActive = true;
    } else {
      remoteNavigationActive = false;
      // Devolve o foco ao vídeo para que o guard de D-pad não segure a barra aberta.
      if (document.activeElement && els.playerWrap.contains(document.activeElement) &&
          document.activeElement.closest(".player-bottom")) {
        try { document.activeElement.blur(); } catch (e) {}
      }
    }
    els.playerWrap.classList.add("active-controls");
    clearTimeout(playerHideTimer);
    // Não inicia a contagem para esconder enquanto o vídeo não estiver realmente
    // em reprodução (carregando, pausado ou com overlay de erro visível).
    if (!els.video || els.video.paused) return;
    playerHideTimer = setTimeout(hidePlayerControls, PLAYER_HIDE_DELAY);
  }

  function hidePlayerControls() {
    if (!els.playerWrap) return;
    // Não some se o foco do D-pad/teclado estiver em um botão da própria barra.
    if (remoteNavigationActive && document.activeElement &&
        els.playerWrap.contains(document.activeElement) &&
        document.activeElement.closest(".player-bottom")) {
      playerHideTimer = setTimeout(hidePlayerControls, PLAYER_HIDE_DELAY);
      return;
    }
    els.playerWrap.classList.remove("active-controls");
  }

  if (els.playerWrap) {
    ["mousemove", "pointerdown", "touchstart", "click", "keydown"].forEach(evt => {
      els.playerWrap.addEventListener(evt, showPlayerControls, { passive: true });
    });
  }

  if (els.video) {
    els.video.addEventListener("playing", showPlayerControls);
    els.video.addEventListener("pause", () => {
      clearTimeout(playerHideTimer);
      if (els.playerWrap) els.playerWrap.classList.add("active-controls");
    });
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
      const isAdult = b.dataset.isAdult === 'true';

      const doOpen = async () => {
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
      };

      if (isAdult && !adultUnlocked) {
        promptAdultPin(() => {
          doOpen();
        });
        return;
      }

      doOpen();
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

    // Rolagem horizontal suave das setas laterais do carrossel (RedPlay / Netflix)
    const railBtn = e.target.closest('[data-rail-scroll]');
    if (railBtn) {
      e.stopPropagation();
      e.preventDefault();
      const dir = Number(railBtn.dataset.railScroll) || 1;
      const track = document.getElementById('vodTrack');
      if (track) {
        track.scrollBy({ left: dir * 550, behavior: 'smooth' });
      }
      return;
    }

    // Favoritar canal direto na grade
    const starEl = e.target.closest('[data-fav-toggle]');
    if (starEl) {
      e.stopPropagation();
      e.preventDefault();
      const sId = starEl.dataset.favToggle;
      if (sId) {
        if (savedFavs.includes(String(sId))) {
          savedFavs = savedFavs.filter(id => id !== String(sId));
          notice("Removido dos favoritos");
        } else {
          savedFavs.push(String(sId));
          notice("Canal salvo nos favoritos");
        }
        localStorage.setItem("nexus_lab_favorites", JSON.stringify(savedFavs));
        draw();
      }
      return;
    }

    // Ações de canais de TV
    if (b.dataset.channelId) {
      const id = b.dataset.channelId;
      const name = b.dataset.channelName;
      playStream(id, name);
      return;
    }

    // Categoria da Interface TV Premium de 3 Colunas (coluna esquerda)
    if (b.dataset.liveCat != null && b.dataset.liveCat !== '') {
      state.liveCat = b.dataset.liveCat;
      state.page = 0;
      draw();
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
        go({ view: 'live', query: '', liveCat: 'all' });
        break;
      case 'sports':
        go({ view: 'sports', query: '', liveCat: 'sports' });
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
        go({ view: 'favorites', query: '', liveCat: 'fav' });
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
    }
  });

  // Atualização dinâmica do painel OSD inferior de detalhes ao navegar nos pôsteres (Padrão RedPlay)
  els.appShell.addEventListener('mouseover', updateVodDetailFromEvent);
  els.appShell.addEventListener('focusin', updateVodDetailFromEvent);

  function updateVodDetailFromEvent(e) {
    const item = e.target.closest('.rail-item');
    if (!item) return;
    const title = item.dataset.vodTitle;
    const plot = item.dataset.vodPlot;
    const year = item.dataset.vodYear;
    const rate = item.dataset.vodRate;
    const id = item.dataset.itemId;
    const type = item.dataset.itemType;

    const elTitle = document.getElementById('vodDetailTitle');
    const elPlot = document.getElementById('vodDetailPlot');
    const elYear = document.getElementById('vodDetailYear');
    const elRate = document.getElementById('vodDetailRating');
    const elPlay = document.getElementById('vodDetailPlayBtn');

    if (elTitle && title) elTitle.textContent = title;
    if (elPlot && plot) elPlot.textContent = plot;
    if (elYear && year) elYear.textContent = year;
    if (elRate && rate) elRate.textContent = '★ ' + rate;
    if (elPlay && id) {
      elPlay.dataset.itemId = id;
      elPlay.dataset.itemType = type;
    }
  }

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

  // Interface TV Premium de 3 Colunas: aponta/foca um canal (mouse, toque ou D-pad)
  // e atualiza a coluna de EPG Detalhado ao vivo, sem redesenhar a tela inteira.
  document.addEventListener('mouseover', e => focusTv3Row(e.target.closest?.('.tv3-chan-row')));
  document.addEventListener('focusin', e => focusTv3Row(e.target.closest?.('.tv3-chan-row')));

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
      // Se for URL externa HTTPS completa (como painelmaster.app, github, imgur, logos), carrega direto!
      if (u.protocol === "https:") return u.href;
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
    try {
      const saved = localStorage.getItem("nexus_play_session");
      if (saved) {
        const p = JSON.parse(saved);
        if (p.expDate) session.expDate = p.expDate;
      }
    } catch(e) {}
    localStorage.setItem("nexus_play_session", JSON.stringify(session));

    if (els.footUser) els.footUser.textContent = `NEXUS PLATFORM • CONTA: ${user.toUpperCase()} (ATIVA)`;

    // Carrega em segundo plano canais, categorias e validação da conta
    try {
      showOverlay("Conectando…", "Carregando grade oficial de canais.");
      const [streams, cats, loginData] = await Promise.all([
        fetchLiveStreams(user, pass),
        fetchCategories(user, pass),
        xtreamLogin(user, pass).catch(() => null)
      ]);
      allStreams = streams;
      allCategories = cats;
      if (loginData && loginData.user_info && loginData.user_info.exp_date) {
        session.expDate = loginData.user_info.exp_date;
        localStorage.setItem("nexus_play_session", JSON.stringify(session));
      }
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

        const urlParams = new URLSearchParams(window.location.search);
        const pairPin = urlParams.get("pair");
        if (pairPin) {
          showOverlay("Conectando sua TV…", `Enviando credenciais para o aparelho (PIN ${pairPin})…`);
          const res = await confirmPairing(pairPin, u, p);
          if (res && res.success) {
            showOverlay("✅ Aparelho Conectado!", "Sua tela foi autorizada com sucesso!");
            setTimeout(() => {
              startSession(u, p);
            }, 400);
            return;
          }
        }
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

  // ---------------- Controle Parental por PIN Rotativo Mensal (+18) ----------------
  const NEXUS_SALT = "nexus_adult_guard_2026";
  const MASTER_OVERRIDE_PIN = "9821"; // PIN mestre administrativo/suporte

  function getMonthlyAdultPin(username) {
    if (!username) return "7887";
    const now = new Date();
    const monthKey = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
    const seed = `${String(username).trim().toLowerCase()}_${monthKey}_${NEXUS_SALT}`;
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = ((hash << 5) - hash) + seed.charCodeAt(i);
      hash |= 0;
    }
    return String(Math.abs(hash) % 9000 + 1000);
  }

  function promptAdultPin(onSuccess) {
    const existing = document.getElementById("adultPinModal");
    if (existing) existing.remove();

    const activeUser = (session && session.user) || (state && state.user) || localStorage.getItem("nexus_last_user") || "sc0u6zlg";
    const correctPin = getMonthlyAdultPin(activeUser);

    const modal = document.createElement("div");
    modal.id = "adultPinModal";
    modal.className = "pin-modal-overlay";
    modal.innerHTML = `
      <div class="pin-modal-card">
        <div style="font-size:32px;margin-bottom:8px;">🔒</div>
        <h3 style="font:700 20px 'Space Grotesk',sans-serif;color:#fff;margin:0 0 6px;">Controle Parental • +18</h3>
        <p style="font-size:13px;color:#9ba59b;margin:0 0 16px;line-height:1.4;">Digite o PIN rotativo mensal liberado na contratação do Add-on Adultos (R$ 4,90).</p>
        <div style="margin-bottom:14px;">
          <input type="password" maxlength="4" id="pinInputVal" placeholder="••••" style="width:140px;text-align:center;font-size:24px;letter-spacing:6px;padding:10px;border-radius:10px;background:#131718;border:1px solid #b7ff3c;color:#fff;outline:none;">
        </div>
        <p id="pinModalErr" style="color:#ff6b6b;font-size:12px;margin:0 0 12px;display:none;"></p>
        <div style="display:flex;gap:10px;justify-content:center;">
          <button type="button" class="btn ghost" id="btnCancelPin" style="padding:10px 18px;border-radius:8px;font-size:13px;min-height:auto;">Cancelar</button>
          <button type="button" class="btn" id="btnConfirmPin" style="padding:10px 22px;border-radius:8px;font-size:13px;min-height:auto;">Liberar Acesso</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const input = document.getElementById("pinInputVal");
    const err = document.getElementById("pinModalErr");
    input.focus();

    const submit = () => {
      const val = input.value.trim();
      if (val === correctPin || val === MASTER_OVERRIDE_PIN) {
        adultUnlocked = true;
        sessionStorage.setItem("nexus_adult_unlocked", "true");
        modal.remove();
        onSuccess();
      } else {
        err.style.display = "block";
        err.textContent = "PIN incorreto ou expirado. Renove seu add-on adulto para obter o código do mês.";
        input.value = "";
        input.focus();
      }
    };

    document.getElementById("btnConfirmPin").onclick = submit;
    input.onkeydown = e => { if (e.key === "Enter") submit(); };
    document.getElementById("btnCancelPin").onclick = () => modal.remove();
  }

  // ---------------- Pareamento QR Code Inteligente ----------------
  async function confirmPairing(pin, user, pass) {
    try {
      const res = await fetch(`${PAIR_BASE}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin, user, pass })
      });
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }

  function initQrCode() {
    const params = new URLSearchParams(window.location.search);
    const pairPin = params.get("pair");

    const qrInlineWrap = document.querySelector(".login-qr-inline");
    if (pairPin && qrInlineWrap) {
      qrInlineWrap.style.display = "none";
      return;
    }

    const pinEl = document.getElementById("qrPinCode");
    const imgEl = document.getElementById("qrCodeImg");
    if (!imgEl || typeof qrcode === "undefined") return;

    let pin = localStorage.getItem("nexus_tv_pin");
    if (!pin) {
      pin = String(Math.floor(1000 + Math.random() * 9000));
      localStorage.setItem("nexus_tv_pin", pin);
    }
    if (pinEl) pinEl.textContent = pin;

    try {
      const pairUrl = `${window.location.origin}${window.location.pathname}?pair=${pin}`;
      const qr = qrcode(0, "M");
      qr.addData(pairUrl);
      qr.make();
      imgEl.src = qr.createDataURL(4, 2);
    } catch (e) {
      console.warn("Falha ao gerar QR Code:", e);
    }

    startPairPolling(pin);
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

  // ---------------- Adaptive Device Engine (Stick / TV Box / Mobile / Web) ----------------
  function detectDeviceProfile() {
    const ua = navigator.userAgent || '';
    const params = new URLSearchParams(window.location.search);
    const forced = params.get('mode');

    let profile = 'desktop';
    if (forced === 'stick' || forced === 'tv') {
      profile = 'stick';
    } else if (/NexusStick|Android TV|AFTT|AFTM|AFTB|FireTV|MiBOX|Chromecast|BRAVIA|SmartTV|Tizen|webOS/i.test(ua)) {
      profile = 'stick';
    } else if (/Android|iPhone|iPad|iPod|Mobile/i.test(ua) && window.innerWidth < 768) {
      profile = 'mobile';
    }

    document.body.dataset.deviceProfile = profile;
    if (profile === 'stick') {
      document.body.classList.add('device-stick', 'ten-foot-ui');
    } else if (profile === 'mobile') {
      document.body.classList.add('device-mobile', 'touch-ui');
    } else {
      document.body.classList.add('device-desktop');
    }
    return profile;
  }

  // ---------------- Boot da Aplicação ----------------
  async function boot() {
    detectDeviceProfile();
    const urlParams = new URLSearchParams(window.location.search);
    const pairParam = urlParams.get("pair");

    // Se o celular abriu a página via QR Code escaneado da TV (?pair=XXXX):
    if (pairParam) {
      try {
        const saved = JSON.parse(localStorage.getItem("nexus_play_session") || "null");
        if (saved && saved.user && saved.pass) {
          showOverlay("Conectando sua TV…", `Enviando acesso para o aparelho (PIN ${pairParam})…`);
          confirmPairing(pairParam, saved.user, saved.pass).then((res) => {
            if (res && res.success) {
              showOverlay("✅ Aparelho Conectado!", "Sua Smart TV foi autorizada e já está dando o play!");
              setTimeout(() => {
                startSession(saved.user, saved.pass);
              }, 400);
            }
          });
          return;
        }
      } catch (e) {}

      // Se ainda não estava logado no celular, atualiza o botão para indicar a TV:
      if (els.btnLogin) {
        els.btnLogin.innerHTML = `Conectar TV (${pairParam}) <span aria-hidden="true">↗</span>`;
      }
    }

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
