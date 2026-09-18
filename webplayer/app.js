/* ============================================================
   NEXUS PLAY — WebPlayer proprietário (play.nexusplay.tv)
   - Consome API Xtream Codes do fornecedor via proxy same-origin
     (/stream/) para eliminar Mixed Content + CORS.
   - Login manual (user/pass) ou automático via querystring:
       ?wallet=<token>   -> token da carteira (ver decodeWallet)
       ?user=X&pass=Y    -> credenciais diretas na URL
       ?url=<m3u8 abs>   -> URL de stream direta (bypassa login)
   ============================================================ */

(() => {
  "use strict";

  // Proxy same-origin que o Nginx repassa para http://atmt.space
  const PROXY_BASE = "/stream";
  // Host real do provedor (apenas para referência/logs, nunca usado
  // para requisições diretas do browser — sempre via PROXY_BASE).
  const UPSTREAM_HOST = "atmt.space";

  const els = {
    gate: document.getElementById("loginGate"),
    inUser: document.getElementById("inUser"),
    inPass: document.getElementById("inPass"),
    btnLogin: document.getElementById("btnLogin"),
    loginErr: document.getElementById("loginErr"),
    video: document.getElementById("video"),
    overlay: document.getElementById("overlay"),
    overlayTitle: document.getElementById("overlayTitle"),
    overlayMsg: document.getElementById("overlayMsg"),
    statusPill: document.getElementById("statusPill"),
    npChannel: document.getElementById("npChannel"),
    npUser: document.getElementById("npUser"),
    channelList: document.getElementById("channelList"),
    searchInput: document.getElementById("searchInput"),
    catSelect: document.getElementById("catSelect"),
    btnFullscreen: document.getElementById("btnFullscreen"),
    btnReload: document.getElementById("btnReload"),
    btnLogout: document.getElementById("btnLogout"),
    sidebar: document.getElementById("sidebar"),
  };

  let hls = null;
  let tsPlayer = null;
  let session = null;       // { user, pass }
  let allStreams = [];      // cache de canais carregados
  let activeStreamId = null;

  // ---------------- Helpers de UI ----------------
  function showOverlay(title, msg) {
    els.overlay.classList.remove("hidden");
    els.overlayTitle.textContent = title || "";
    els.overlayMsg.textContent = msg || "";
  }
  function hideOverlay() { els.overlay.classList.add("hidden"); }
  function setStatus(text, kind) {
    els.statusPill.textContent = "● " + text;
    els.statusPill.className = "status-pill" + (kind ? " " + kind : "");
  }
  function showLoginError(msg) {
    els.loginErr.textContent = msg;
    els.loginErr.style.display = "block";
  }

  // ---------------- Decodificação do token da carteira ----------------
  // Formatos aceitos (nesta ordem de tentativa):
  //  1) base64url(JSON) -> {"user":"...","pass":"...","exp":<unix opcional>}
  //  2) base64url("user:pass")
  function b64urlDecode(str) {
    let s = str.replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    return decodeURIComponent(
      atob(s).split("").map(c => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    );
  }
  function decodeWallet(token) {
    if (!token) return null;
    let raw;
    try { raw = b64urlDecode(token); } catch (e) { return null; }
    // tentativa 1: JSON
    try {
      const obj = JSON.parse(raw);
      if (obj.exp && Date.now() / 1000 > Number(obj.exp)) {
        throw new Error("wallet token expirado");
      }
      const user = obj.user || obj.u || obj.username;
      const pass = obj.pass || obj.p || obj.password;
      if (user && pass) return { user, pass };
    } catch (e) { /* segue para tentativa 2 */ }
    // tentativa 2: "user:pass"
    if (raw.includes(":")) {
      const [user, ...rest] = raw.split(":");
      const pass = rest.join(":");
      if (user && pass) return { user, pass };
    }
    return null;
  }

  // ---------------- Reescrita de URLs upstream -> proxy seguro ----------------
  // Qualquer URL absoluta apontando para o provedor HTTP é reescrita para
  // o caminho relativo /stream/... servido em HTTPS pelo mesmo domínio do
  // player, eliminando Mixed Content e CORS de uma vez.
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

  // ---------------- Xtream Codes API (via proxy) ----------------
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

  function buildLiveUrl(user, pass, streamId, ext) {
    ext = ext || "m3u8";
    // Formato padrão Xtream Codes: /live/USER/PASS/STREAM_ID.ext
    return apiUrl(`/live/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${streamId}.${ext}`);
  }

  // ---------------- Player HLS & MPEG-TS ----------------
  let reconnectTimer = null;

  function destroyPlayer() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
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
      logoEl.src = stream && stream.stream_icon ? toProxied(stream.stream_icon) : "./design/nexus.svg";
      logoEl.onerror = () => { logoEl.src = "./design/nexus.svg"; };
    }

    const cleanName = (label || (stream && stream.name) || "Canal Nexus").replace(/</g, "&lt;");
    if (nameEl) nameEl.innerHTML = cleanName;

    const is4k = /4k|uhd/i.test(label || (stream && stream.name) || "");
    const isFhd = /fhd|1080/i.test(label || (stream && stream.name) || "");
    if (resEl) {
      resEl.textContent = is4k ? "4K" : (isFhd ? "FHD" : "HD");
      resEl.className = `osd-res ${is4k ? "res-4k" : (isFhd ? "res-fhd" : "")}`;
    }

    if (progEl) {
      progEl.textContent = stream && stream.category_name ? `${stream.category_name} • Transmissão ao Vivo` : "Transmissão Oficial Nexus";
    }

    osd.classList.add("show");
    if (window.skyOsdTimer) clearTimeout(window.skyOsdTimer);
    window.skyOsdTimer = setTimeout(() => {
      osd.classList.remove("show");
    }, 4500);
  }

  function playStream(streamId, label) {
    destroyPlayer();
    showOverlay("Carregando canal…", label || "");
    setStatus("carregando", "");

    const video = els.video;
    const user = session ? session.user : "";
    const pass = session ? session.pass : "";

    const tsUrl = toProxied(buildLiveUrl(user, pass, streamId, "ts"));

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
          autoCleanupMaxBackwardDuration: 30,
          autoCleanupMinBackwardDuration: 15,
          stashInitialSize: 512 * 1024
        });

        tsPlayer.attachMediaElement(video);
        tsPlayer.load();

        let playStarted = false;
        const startPlayback = () => {
          if (playStarted) return;
          playStarted = true;
          hideOverlay();
          video.controls = true;
          setStatus("ao vivo", "live");
          showSkyOsd(streamId, label);
          // Dispara os anúncios transitórios oficiais PixGet
          setTimeout(() => {
            showLowerThird(10000);
          }, 6000);
          startCornerBadgeLoop();
          const playPromise = video.play();
          if (playPromise !== undefined) {
            playPromise.catch((err) => {
              if (err.name === "NotAllowedError") {
                video.muted = true;
                video.play().catch(() => {});
                showOverlay("Clique para ativar o som 🔊", "O navegador requer um clique para liberar o áudio.");
                const unmute = () => {
                  video.muted = false;
                  hideOverlay();
                  window.removeEventListener("click", unmute);
                  video.removeEventListener("click", unmute);
                };
                window.addEventListener("click", unmute, { once: true });
                video.addEventListener("click", unmute, { once: true });
              }
            });
          }
        };

        video.onloadeddata = startPlayback;
        video.onplaying = startPlayback;
        video.oncanplay = startPlayback;

        tsPlayer.on(window.mpegts.Events.ERROR, (errType, errDetail, errInfo) => {
          console.warn("mpegts erro:", errType, errDetail, errInfo);
          if (!playStarted) {
            destroyPlayer();
            if (errInfo && errInfo.code === 429) {
              showOverlay("Conexão ocupada", "Liberando conexão e reconectando em 3s…");
              setStatus("reconectando", "err");
              reconnectTimer = setTimeout(() => playStream(streamId, label), 3500);
            } else {
              showOverlay("Erro ao carregar canal", "Tentando reconectar…");
              setStatus("erro", "err");
              reconnectTimer = setTimeout(() => playStream(streamId, label), 3000);
            }
          }
        });
        return;
      } catch (err) {
        console.warn("Erro ao iniciar mpegts:", err);
      }
    }

    // Fallback HLS apenas para navegadores que não suportam MSE (ex: Safari iOS nativo)
    const m3u8Url = toProxied(buildLiveUrl(user, pass, streamId, "m3u8"));
    fallbackHls(m3u8Url, label);
  }

  function fallbackHls(finalUrl, label) {
    const video = els.video;
    if (window.Hls && window.Hls.isSupported()) {
      hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 60,
        maxBufferLength: 30,
        enableWorker: true,
        xhrSetup: function(xhr, url) {
          if (url.startsWith("http://atmt.space")) {
            xhr.open("GET", url.replace("http://atmt.space", "/stream"), true);
          }
        }
      });
      hls.loadSource(finalUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        hideOverlay();
        setStatus("ao vivo", "live");
        video.play().catch(() => {});
      });
      hls.on(Hls.Events.ERROR, (event, data) => {
        if (!data.fatal) return;
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            showOverlay("Erro de rede", "Tentando reconectar ao stream…");
            setStatus("reconectando", "err");
            setTimeout(() => { try { hls.startLoad(); } catch (e) {} }, 1500);
            break;
          case Hls.ErrorTypes.MEDIA_ERROR:
            showOverlay("Erro de mídia", "Recuperando decodificador…");
            try { hls.recoverMediaError(); } catch (e) {}
            break;
          default:
            showOverlay("Não foi possível reproduzir", "Verifique a conexão ou tente outro canal.");
            setStatus("erro", "err");
            destroyPlayer();
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari / iOS: HLS nativo
      video.src = finalUrl;
      video.addEventListener("loadedmetadata", () => {
        hideOverlay();
        setStatus("ao vivo", "live");
        video.play().catch(() => {});
      }, { once: true });
      video.addEventListener("error", () => {
        showOverlay("Não foi possível reproduzir", "Verifique a conexão ou tente outro canal.");
        setStatus("erro", "err");
      }, { once: true });
    } else {
      showOverlay("Navegador não suportado", "Seu navegador não suporta reprodução HLS ou MPEG-TS.");
      setStatus("erro", "err");
    }
  }

  // ---------------- Favoritos (LocalStorage) ----------------
  function getFavorites() {
    try {
      const favs = JSON.parse(localStorage.getItem("nexus_favorites") || "[]");
      return Array.isArray(favs) ? favs : [];
    } catch (e) {
      return [];
    }
  }

  function toggleFavorite(streamId) {
    const favs = getFavorites();
    const strId = String(streamId);
    const index = favs.indexOf(strId);
    if (index >= 0) {
      favs.splice(index, 1);
    } else {
      favs.push(strId);
    }
    localStorage.setItem("nexus_favorites", JSON.stringify(favs));
    updateFavBadge();
  }

  function updateFavBadge() {
    const badge = document.getElementById("favCounterBadge");
    if (!badge) return;
    const count = getFavorites().length;
    if (count > 0) {
      badge.textContent = String(count);
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  }

  // ---------------- Lista de canais ----------------
  function renderChannelList(streams) {
    const q = (els.searchInput.value || "").toLowerCase().trim();
    const cat = els.catSelect.value;
    const favs = getFavorites();

    const btnQuickSports = document.getElementById("btnQuickSports");
    const btnQuickFavs = document.getElementById("btnQuickFavs");
    if (btnQuickSports) btnQuickSports.classList.toggle("active", cat === "sports_today");
    if (btnQuickFavs) btnQuickFavs.classList.toggle("active", cat === "favorites");

    const filtered = streams.filter(s => {
      if (cat === "favorites") {
        if (!favs.includes(String(s.stream_id))) return false;
      } else if (cat === "sports_today") {
        const name = String(s.name || "").toLowerCase();
        const catName = String(s.category_name || "").toLowerCase();
        const isMatch = name.includes(" x ") || name.includes(" vs ") || /\b\d{1,2}:\d{2}\b/.test(name);
        const isSport = catName.includes("jogo") || catName.includes("futebol") || catName.includes("premiere") || catName.includes("sportv") || catName.includes("espn") || catName.includes("dazn") || catName.includes("cazé") || catName.includes("conmebol") || catName.includes("brasileir");
        if (!isMatch && !isSport && String(s.category_id) !== "sports_today") return false;
      } else if (cat && String(s.category_id) !== String(cat)) {
        return false;
      }
      if (q && !String(s.name || "").toLowerCase().includes(q)) return false;
      return true;
    });

    if (!filtered.length) {
      const msg = cat === "favorites"
        ? "Nenhum canal favoritado ainda.<br>Clique no símbolo de estrela ao lado de qualquer canal para salvar aqui."
        : cat === "sports_today"
        ? "Nenhuma partida esportiva listada no momento."
        : "Nenhum canal encontrado.";
      els.channelList.innerHTML = `<div class="empty-hint">${msg}</div>`;
      return;
    }

    els.channelList.innerHTML = filtered.slice(0, 400).map((s, idx) => {
      const logo = s.stream_icon ? toProxied(s.stream_icon) : "";
      const active = String(s.stream_id) === String(activeStreamId) ? " active" : "";
      const finalLogo = logo || "/favicon.png";
      const isFav = favs.includes(String(s.stream_id));
      const starFill = isFav ? "var(--green)" : "none";
      const starStroke = isFav ? "var(--green)" : "#a2b0a2";

      const numStr = s.num ? String(s.num).padStart(3, "0") : String(idx + 1).padStart(3, "0");
      const name = String(s.name || "Canal");
      const is4k = /4k|uhd/i.test(name);
      const isFhd = /fhd|1080/i.test(name);
      const resBadge = is4k ? `<span class="res-badge res-4k">4K</span>` : (isFhd ? `<span class="res-badge res-fhd">FHD</span>` : `<span class="res-badge">HD</span>`);

      return `<div class="chan${active}" data-id="${s.stream_id}" tabindex="0">
        <span class="num-badge">${numStr}</span>
        <img class="logo" src="${finalLogo}" loading="lazy" onerror="this.onerror=null;this.src='/favicon.png';">
        <span class="name">${name.replace(/</g, "&lt;")}</span>
        ${resBadge}
        <button type="button" class="btn-fav-star${isFav ? ' is-fav' : ''}" data-fav-id="${s.stream_id}" title="${isFav ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}" aria-label="Favoritar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="${starFill}" stroke="${starStroke}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
          </svg>
        </button>
      </div>`;
    }).join("");

    els.channelList.querySelectorAll(".btn-fav-star").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-fav-id");
        toggleFavorite(id);
        renderChannelList(streams);
      });
    });

    els.channelList.querySelectorAll(".chan").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".btn-fav-star")) return;
        const id = el.getAttribute("data-id");
        const stream = streams.find(s => String(s.stream_id) === String(id));
        if (!stream) return;
        activeStreamId = id;
        els.npChannel.textContent = stream.name || "Canal";
        localStorage.setItem("nexus_last_stream_id", String(stream.stream_id));
        renderChannelList(streams);
        if (window.innerWidth <= 860) els.sidebar.classList.remove("open");
        playStream(stream.stream_id, stream.name);
      });
    });
  }

  // ---------------- Categorias no padrão dos canais (sem popup / rola até o fim) ----------------
  let allCategories = [];
  let currentViewMode = "channels"; // "channels" | "categories"

  const catTrigger = document.getElementById("catDropdownTrigger");
  const catLabel = document.getElementById("catCurrentLabel");

  function renderCategoryList() {
    const q = (els.searchInput.value || "").toLowerCase().trim();
    const activeCat = els.catSelect.value;
    const favCount = getFavorites().length;

    const specialItems = [
      { category_id: "favorites", category_name: `Favoritos (${favCount})`, isSpecial: "fav" },
      { category_id: "sports_today", category_name: "Jogos do Dia", isSpecial: "sports" },
      { category_id: "", category_name: "Todas as categorias" }
    ];

    const items = [
      ...specialItems,
      ...allCategories
    ].filter(c => !q || (c.category_name || "").toLowerCase().includes(q));

    if (!items.length) {
      els.channelList.innerHTML = `<div class="empty-hint">Nenhuma categoria encontrada.</div>`;
      return;
    }

    els.channelList.innerHTML = items.map(c => {
      const active = String(c.category_id) === String(activeCat) ? " active" : "";
      let iconHtml = `<img src="./design/nexus.svg" alt="" class="cat-n-icon">`;
      if (c.isSpecial === "fav") {
        iconHtml = `<svg width="15" height="15" viewBox="0 0 24 24" fill="var(--green)" stroke="var(--green)" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;
      } else if (c.isSpecial === "sports") {
        iconHtml = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="12 6 15.5 8.5 14 12.5 10 12.5 8.5 8.5 12 6"></polygon></svg>`;
      }

      return `<div class="chan cat-card${active}" data-cat-id="${c.category_id}">
        <div class="cat-icon-badge">
          ${iconHtml}
        </div>
        <span class="name">${(c.category_name || "Geral").replace(/</g, "&lt;")}</span>
      </div>`;
    }).join("");

    els.channelList.querySelectorAll(".chan.cat-card").forEach(el => {
      el.addEventListener("click", () => {
        const catId = el.getAttribute("data-cat-id");
        els.catSelect.value = catId;
        const name = el.querySelector(".name").textContent;
        if (catLabel) catLabel.textContent = name;

        // Retorna para visualização de canais daquela categoria
        currentViewMode = "channels";
        if (catTrigger) catTrigger.classList.remove("active-mode");
        renderChannelList(allStreams);
        resetAutoRetractTimer();
      });
    });
  }

  if (catTrigger) {
    catTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      currentViewMode = currentViewMode === "categories" ? "channels" : "categories";
      if (currentViewMode === "categories") {
        catTrigger.classList.add("active-mode");
        renderCategoryList();
      } else {
        catTrigger.classList.remove("active-mode");
        renderChannelList(allStreams);
      }
      resetAutoRetractTimer();
    });
  }

  // Atalhos Rápidos (Jogos do Dia e Favoritos)
  const btnQuickSports = document.getElementById("btnQuickSports");
  const btnQuickFavs = document.getElementById("btnQuickFavs");

  if (btnQuickSports) {
    btnQuickSports.addEventListener("click", () => {
      if (els.catSelect.value === "sports_today") {
        els.catSelect.value = "";
        if (catLabel) catLabel.textContent = "Todas as categorias";
      } else {
        els.catSelect.value = "sports_today";
        if (catLabel) catLabel.textContent = "Jogos do Dia";
      }
      currentViewMode = "channels";
      if (catTrigger) catTrigger.classList.remove("active-mode");
      renderChannelList(allStreams);
      resetAutoRetractTimer();
    });
  }

  if (btnQuickFavs) {
    btnQuickFavs.addEventListener("click", () => {
      if (els.catSelect.value === "favorites") {
        els.catSelect.value = "";
        if (catLabel) catLabel.textContent = "Todas as categorias";
      } else {
        els.catSelect.value = "favorites";
        if (catLabel) catLabel.textContent = "Favoritos";
      }
      currentViewMode = "channels";
      if (catTrigger) catTrigger.classList.remove("active-mode");
      renderChannelList(allStreams);
      resetAutoRetractTimer();
    });
  }

  // ---------------- Relógio Digital de Topo (Estilo BTV / Sky) ----------------
  function updateTvClock() {
    const timeEl = document.getElementById("tvTime");
    const dateEl = document.getElementById("tvDate");
    if (!timeEl || !dateEl) return;
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    timeEl.textContent = `${h}:${m}`;
    const days = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
    const months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    dateEl.textContent = `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]}`;
  }
  setInterval(updateTvClock, 1000);
  updateTvClock();

  // ---------------- Navegação por Controle Remoto (Smart TV D-Pad) ----------------
  let focusedChannelIndex = -1;
  window.addEventListener("keydown", (e) => {
    if (document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA")) return;
    const chanElements = Array.from(els.channelList.querySelectorAll(".chan"));
    if (!chanElements.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      focusedChannelIndex = Math.min(chanElements.length - 1, focusedChannelIndex + 1);
      updateTvFocus(chanElements);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      focusedChannelIndex = Math.max(0, focusedChannelIndex - 1);
      updateTvFocus(chanElements);
    } else if ((e.key === "Enter" || e.key === " ") && focusedChannelIndex >= 0) {
      e.preventDefault();
      chanElements[focusedChannelIndex].click();
    }
  });

  function updateTvFocus(elements) {
    elements.forEach((el, i) => {
      if (i === focusedChannelIndex) {
        el.classList.add("tv-focused");
        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
      } else {
        el.classList.remove("tv-focused");
      }
    });
  }

  // ---------------- Abas de Conteúdo no Topo (BTV / RedPlay Launcher) ----------------
  const tvTabs = document.querySelectorAll(".tv-tab-btn");
  let currentActiveTab = "live"; // "live" | "sports" | "movies" | "series" | "favs"

  tvTabs.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      tvTabs.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentActiveTab = tab;

      if (tab === "live") {
        els.catSelect.value = "";
        if (catLabel) catLabel.textContent = "Todas as categorias";
        renderChannelList(allStreams);
      } else if (tab === "sports") {
        els.catSelect.value = "sports_today";
        if (catLabel) catLabel.textContent = "Jogos do Dia";
        renderChannelList(allStreams);
      } else if (tab === "favs") {
        els.catSelect.value = "favorites";
        if (catLabel) catLabel.textContent = "Meus Favoritos";
        renderChannelList(allStreams);
      } else if (tab === "movies") {
        loadVodSection("movie");
      } else if (tab === "series") {
        loadVodSection("series");
      }
    });
  });

  async function loadVodSection(type) {
    if (!session) return;
    const title = type === "series" ? "Séries & Temporadas" : "Cine Nexus (Filmes)";
    if (catLabel) catLabel.textContent = title;
    els.channelList.innerHTML = `<div class="empty-hint"><div class="spinner" style="margin:0 auto 12px;width:32px;height:32px;"></div>Carregando catálogo de ${type === "series" ? "séries" : "filmes"}…</div>`;

    try {
      const catAction = type === "series" ? "get_series_categories" : "get_vod_categories";
      const catRes = await fetch(`/stream/player_api.php?username=${encodeURIComponent(session.user)}&password=${encodeURIComponent(session.pass)}&action=${catAction}`);
      const cats = await catRes.json();
      const firstCat = Array.isArray(cats) && cats.length ? cats[0].category_id : "";

      const streamAction = type === "series" ? "get_series" : "get_vod_streams";
      const vodRes = await fetch(`/stream/player_api.php?username=${encodeURIComponent(session.user)}&password=${encodeURIComponent(session.pass)}&action=${streamAction}&category_id=${encodeURIComponent(firstCat)}`);
      const vods = await vodRes.json();

      if (!Array.isArray(vods) || !vods.length) {
        els.channelList.innerHTML = `<div class="empty-hint">Nenhum conteúdo sob demanda encontrado no momento.</div>`;
        return;
      }

      els.channelList.innerHTML = vods.slice(0, 150).map(v => {
        const cover = v.stream_icon || v.cover || "/favicon.png";
        const vTitle = (v.name || "Filme").replace(/</g, "&lt;");
        const rating = v.rating ? `★ ${v.rating}` : (v.year || "VOD");
        return `<div class="chan vod-card" data-vod-id="${v.stream_id || v.series_id}" data-type="${type}" data-ext="${v.container_extension || 'mp4'}">
          <img class="logo vod-poster" src="${cover}" loading="lazy" onerror="this.onerror=null;this.src='/favicon.png';">
          <div style="flex:1;min-width:0;">
            <span class="name" style="font-weight:600;">${vTitle}</span>
            <div style="font-size:10px;color:var(--muted);margin-top:2px;">${rating} • ${type === 'series' ? 'Série' : 'Cinema'}</div>
          </div>
        </div>`;
      }).join("");

      els.channelList.querySelectorAll(".chan.vod-card").forEach(el => {
        el.addEventListener("click", () => {
          const id = el.getAttribute("data-vod-id");
          const vType = el.getAttribute("data-type");
          const vExt = el.getAttribute("data-ext");
          const vName = el.querySelector(".name").textContent;
          if (vType === "movie") {
            playVodMovie(id, vName, vExt);
          } else {
            showOverlay(vName, "Abra um episódio para reproduzir.");
            setTimeout(hideOverlay, 2000);
          }
        });
      });
    } catch (e) {
      els.channelList.innerHTML = `<div class="empty-hint">Erro ao carregar catálogo. Retorne para TV ao Vivo.</div>`;
    }
  }

  function playVodMovie(streamId, name, ext) {
    destroyPlayer();
    showOverlay("Reproduzindo Filme…", name);
    setStatus("reproduzindo", "live");
    els.npChannel.textContent = name;
    showSkyOsd(streamId, name);

    const user = session ? session.user : "";
    const pass = session ? session.pass : "";
    const movieUrl = `/stream/movie/${encodeURIComponent(user)}/${encodeURIComponent(pass)}/${encodeURIComponent(streamId)}.${ext || 'mp4'}`;
    els.video.src = movieUrl;
    els.video.controls = true;
    els.video.play().then(() => {
      hideOverlay();
    }).catch(() => {
      hideOverlay();
    });
  }

  function renderCategories(cats) {
    allCategories = Array.isArray(cats) ? cats : [];
    if (els.catSelect) els.catSelect.value = "";
  }

  // ---------------- Fluxo de sessão ----------------
  async function startSession(user, pass, opts) {
    opts = opts || {};
    els.gate.classList.add("hidden");
    session = { user, pass };
    localStorage.setItem("nexus_play_session", JSON.stringify(session));

    try {
      // Valida credenciais em paralelo sem bloquear a reprodução imediata
    xtreamLogin(user, pass).then(login => {
      if (login && login.user_info) {
        els.npUser.textContent = `Conta: ${user}${login.user_info.exp_date ? " • expira " + new Date(login.user_info.exp_date * 1000).toLocaleDateString("pt-BR") : ""}`;
      }
    }).catch(err => {
      console.warn("Aviso na validação:", err);
    });

    // 1. Tenta carregar do cache local imediatamente para iniciar o play em 0.05s
    let hasCached = false;
    try {
      const cachedS = sessionStorage.getItem("nexus_cached_streams");
      const cachedC = sessionStorage.getItem("nexus_cached_cats");
      if (cachedS) {
        const parsedS = JSON.parse(cachedS);
        if (Array.isArray(parsedS) && parsedS.length) {
          allStreams = parsedS;
          if (cachedC) renderCategories(JSON.parse(cachedC));
          renderChannelList(allStreams);
          hasCached = true;

          const lastId = localStorage.getItem("nexus_last_stream_id") || allStreams[0].stream_id;
          const target = allStreams.find(s => String(s.stream_id) === String(lastId)) || allStreams[0];
          activeStreamId = target.stream_id;
          els.npChannel.textContent = target.name || "Canal";
          playStream(target.stream_id, target.name);
        }
      }
    } catch (e) {}

    if (!hasCached) {
      showOverlay("Conectando TV…", "Iniciando transmissão ao vivo.");
    }

      // 2. Busca na rede (atualiza cache e lista em segundo plano)
      Promise.all([
        fetchLiveStreams(user, pass).catch(() => []),
        fetchCategories(user, pass).catch(() => []),
      ]).then(([streams, cats]) => {
        if (Array.isArray(streams) && streams.length) {
          allStreams = streams;
          try {
            sessionStorage.setItem("nexus_cached_streams", JSON.stringify(streams));
            if (Array.isArray(cats)) sessionStorage.setItem("nexus_cached_cats", JSON.stringify(cats));
          } catch (e) {}
          renderCategories(Array.isArray(cats) ? cats : []);
          renderChannelList(allStreams);

          if (opts.directUrl) {
            fallbackHls(opts.directUrl, "Stream direto");
          } else if (!hasCached && !activeStreamId) {
            const lastId = localStorage.getItem("nexus_last_stream_id") || allStreams[0].stream_id;
            const target = allStreams.find(s => String(s.stream_id) === String(lastId)) || allStreams[0];
            activeStreamId = target.stream_id;
            els.npChannel.textContent = target.name || "Canal";
            playStream(target.stream_id, target.name);
          }
        } else if (!hasCached) {
          hideOverlay();
          setStatus("conectado", "live");
        }
      });
    } catch (err) {
      console.error(err);
      els.gate.classList.remove("hidden");
      showLoginError(err.message || "Falha ao autenticar.");
      setStatus("erro de login", "err");
      hideOverlay();
    }
  }

  function logout() {
    destroyPlayer();
    localStorage.removeItem("nexus_play_session");
    localStorage.removeItem("nexus_tv_pin");
    session = null;
    activeStreamId = null;
    els.video.removeAttribute("src");
    els.npChannel.textContent = "Nenhum canal selecionado";
    els.npUser.textContent = "";
    els.channelList.innerHTML = `<div class="empty-hint">Faça login para carregar a lista de canais.</div>`;
    els.gate.classList.remove("hidden");
    setStatus("desconectado", "");
    hideOverlay();
    initQrCode();
  }

  // ---------------- Eventos de UI ----------------
  els.btnLogin.addEventListener("click", async () => {
    const user = els.inUser.value.trim();
    const pass = els.inPass.value;
    els.loginErr.style.display = "none";
    if (!user || !pass) { showLoginError("Informe usuário e senha."); return; }

    const params = new URLSearchParams(window.location.search);
    const pairPin = params.get("pair");
    if (pairPin) {
      showOverlay("Conectando sua TV…", `Enviando credenciais para o aparelho (PIN ${pairPin})…`);
      const res = await confirmPairing(pairPin, user, pass);
      if (res && res.success) {
        showOverlay("✅ Aparelho Conectado!", "Sua tela foi autorizada com sucesso!");
        setTimeout(() => {
          startSession(user, pass);
        }, 300);
        return;
      }
    }

    startSession(user, pass);
  });
  [els.inUser, els.inPass].forEach(inp => inp.addEventListener("keydown", e => {
    if (e.key === "Enter") els.btnLogin.click();
  }));
  // Toggle exibir/ocultar senha
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

  els.btnLogout.addEventListener("click", logout);
  els.btnReload.addEventListener("click", () => {
    if (session && activeStreamId) playStream(activeStreamId, els.npChannel.textContent);
  });
  const playerWrap = els.video.closest(".player-wrap");
  const btnZoom = document.getElementById("btnZoom");
  const zoomToast = document.getElementById("zoomToast");
  let zoomToastTimer = null;

  function showZoomToast(text) {
    if (!zoomToast) return;
    zoomToast.textContent = text;
    zoomToast.classList.add("show");
    if (zoomToastTimer) clearTimeout(zoomToastTimer);
    zoomToastTimer = setTimeout(() => {
      zoomToast.classList.remove("show");
    }, 1200);
  }

  function toggleZoom() {
    if (!playerWrap) return;
    const isZoomed = playerWrap.classList.toggle("zoom-fill");
    localStorage.setItem("nexus_zoom_mode", isZoomed ? "fill" : "fit");
    showZoomToast(isZoomed ? "⛶ Ampliado para preencher a tela" : "⊡ Ajustado à tela (original)");
  }

  if (localStorage.getItem("nexus_zoom_mode") === "fill" && playerWrap) {
    playerWrap.classList.add("zoom-fill");
  }

  if (btnZoom) btnZoom.addEventListener("click", toggleZoom);

  // Duplo toque (mobile) e duplo clique (desktop) no vídeo para ampliar como no YouTube
  let lastTouchEndTime = 0;
  if (playerWrap) {
    playerWrap.addEventListener("touchend", (e) => {
      if (e.target.closest("button") || e.target.closest("a")) return;
      const now = Date.now();
      const delta = now - lastTouchEndTime;
      if (delta > 40 && delta < 380) {
        e.preventDefault();
        toggleZoom();
        lastTouchEndTime = 0;
        return;
      }
      lastTouchEndTime = now;
    }, { passive: false });

    playerWrap.addEventListener("dblclick", (e) => {
      if (e.target.closest("button") || e.target.closest("a")) return;
      e.preventDefault();
      toggleZoom();
    });
  }

  els.btnFullscreen.addEventListener("click", () => {
    if (!playerWrap) return;
    const isFull = playerWrap.classList.contains("fullscreen-mode") || !!document.fullscreenElement || !!document.webkitFullscreenElement;

    if (!isFull) {
      playerWrap.classList.add("fullscreen-mode");
      document.body.classList.add("in-fullscreen");
      const req = playerWrap.requestFullscreen || playerWrap.webkitRequestFullscreen || playerWrap.mozRequestFullScreen || playerWrap.msRequestFullscreen;
      if (req) req.call(playerWrap).catch(() => {});
    } else {
      playerWrap.classList.remove("fullscreen-mode");
      document.body.classList.remove("in-fullscreen");
      const exit = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
      if (exit && (document.fullscreenElement || document.webkitFullscreenElement)) {
        exit.call(document).catch(() => {});
      }
    }
  });

  ["fullscreenchange", "webkitfullscreenchange"].forEach(evt => {
    document.addEventListener(evt, () => {
      if (!document.fullscreenElement && !document.webkitFullscreenElement && playerWrap) {
        playerWrap.classList.remove("fullscreen-mode");
        document.body.classList.remove("in-fullscreen");
      }
    });
  });
  els.searchInput.addEventListener("input", () => {
    if (currentViewMode === "categories") {
      renderCategoryList();
    } else {
      renderChannelList(allStreams);
    }
  });
  els.catSelect.addEventListener("change", () => renderChannelList(allStreams));

  // =========================================================================
  // GESTÃO DE ANÚNCIOS OFICIAIS NEXUS (100% TEMPORÁRIOS / NENHUM FIXO)
  // =========================================================================
  const elAdBadge = document.getElementById("adCornerBadge");
  const elAdLt = document.getElementById("adLowerThird");
  const elBtnAdLtClose = document.getElementById("btnAdLtClose");
  const elBillboardImgLink = document.getElementById("adBbImgLink");

  // 1. CORNER BADGE (Canto Superior Direito): 14s visível -> 35s apagado
  let badgeLoopActive = false;
  function startCornerBadgeLoop() {
    if (badgeLoopActive || !elAdBadge) return;
    badgeLoopActive = true;
    function cycleBadge() {
      elAdBadge.classList.add("visible");
      setTimeout(() => {
        elAdBadge.classList.remove("visible");
        setTimeout(cycleBadge, 35000); // 35 segundos completamente invisível
      }, 14000); // 14 segundos visível
    }
    setTimeout(cycleBadge, 4000);
  }

  // 2. LOWER-THIRD (Rodapé do Vídeo): 10s visível, repete a cada 2.5 min
  let ltTimer = null;
  function showLowerThird(durationMs = 10000) {
    if (!elAdLt) return;
    elAdLt.classList.add("active");
    if (ltTimer) clearTimeout(ltTimer);
    ltTimer = setTimeout(() => {
      elAdLt.classList.remove("active");
      ltTimer = null;
    }, durationMs);
  }

  function hideLowerThird() {
    if (elAdLt) elAdLt.classList.remove("active");
    if (ltTimer) { clearTimeout(ltTimer); ltTimer = null; }
  }

  if (elBtnAdLtClose) {
    elBtnAdLtClose.addEventListener("click", (e) => {
      e.stopPropagation();
      hideLowerThird();
    });
  }

  // Aciona automaticamente o Lower-Third a cada 60s se o vídeo estiver tocando
  setInterval(() => {
    if (els.video && !els.video.paused) {
      showLowerThird(10000);
    }
  }, 60000);

  // 3. BILLBOARD VERTICAL (Barra Lateral): 12s visível -> 22s apagado (preto limpo)
  function startBillboardLoop() {
    if (!elBillboardImgLink) return;
    function cycleBillboard() {
      elBillboardImgLink.classList.add("visible");
      setTimeout(() => {
        elBillboardImgLink.classList.remove("visible");
        setTimeout(cycleBillboard, 22000); // 22 segundos completamente apagado (preto limpo)
      }, 12000); // 12 segundos visível
    }
    setTimeout(cycleBillboard, 1500);
  }
  startBillboardLoop();

  // Botão Ícone de Recolher/Expandir Canais na Barra Lateral
  const btnToggleChannels = document.getElementById("btnToggleChannels");
  const sidebar = document.getElementById("sidebar");

  // Timer de Auto-Recolhimento (após 2s de inatividade na lista expandida)
  let autoRetractTimer = null;

  function resetAutoRetractTimer() {
    if (autoRetractTimer) {
      clearTimeout(autoRetractTimer);
      autoRetractTimer = null;
    }
    // Se estiver no modo de categorias, volta para os canais após 3s sem interação
    if (currentViewMode === "categories") {
      autoRetractTimer = setTimeout(() => {
        if (currentViewMode === "categories") {
          currentViewMode = "channels";
          if (catTrigger) catTrigger.classList.remove("active-mode");
          renderChannelList(allStreams);
        }
      }, 3000);
      return;
    }
    // Se a lista estiver EXPANDIDA (não tem channels-retracted)
    if (sidebar && !sidebar.classList.contains("channels-retracted")) {
      autoRetractTimer = setTimeout(() => {
        sidebar.classList.add("channels-retracted");
        if (btnToggleChannels) {
          btnToggleChannels.setAttribute("aria-expanded", "false");
          btnToggleChannels.title = "Expandir lista de canais";
        }
      }, 3000); // 3 segundos sem interação
    }
  }

  // Interações na barra lateral reiniciam o timer de 2s
  if (sidebar) {
    ["mousemove", "scroll", "keydown", "touchstart", "click"].forEach(evt => {
      sidebar.addEventListener(evt, resetAutoRetractTimer, { passive: true });
    });
  }

  if (btnToggleChannels && sidebar) {
    btnToggleChannels.addEventListener("click", () => {
      const isRetracted = sidebar.classList.toggle("channels-retracted");
      btnToggleChannels.setAttribute("aria-expanded", isRetracted ? "false" : "true");
      btnToggleChannels.title = isRetracted ? "Expandir lista de canais" : "Recolher lista para ver anúncio";
      if (!isRetracted) {
        resetAutoRetractTimer();
      }
    });

    els.searchInput.addEventListener("focus", () => {
      if (sidebar.classList.contains("channels-retracted")) {
        sidebar.classList.remove("channels-retracted");
        btnToggleChannels.setAttribute("aria-expanded", "true");
        btnToggleChannels.title = "Recolher lista para ver anúncio";
      }
      resetAutoRetractTimer();
    });
  }

  // ---------------- Sistema de Login Smart TV / QR Code Compacto ----------------
  const qrCodeImg = document.getElementById("qrCodeImg");
  const qrPinCode = document.getElementById("qrPinCode");
  let pairPollInterval = null;

  function stopPairPolling() {
    if (pairPollInterval) {
      clearInterval(pairPollInterval);
      pairPollInterval = null;
    }
  }

  let activePairPin = null;

  async function checkPairStatus(pin) {
    if (!els.gate || els.gate.classList.contains("hidden")) {
      stopPairPolling();
      return;
    }
    try {
      const res = await fetch(`/pair/status?pin=${encodeURIComponent(pin)}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "paired" && data.user && data.pass) {
        stopPairPolling();
        // Consome e invalida o PIN imediatamente para evitar login fantasma
        fetch("/pair/consume", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin })
        }).catch(() => {});
        localStorage.removeItem("nexus_tv_pin");
        showOverlay("Pareamento Concluído!", "Celular conectado com sucesso. Iniciando TV…");
        startSession(data.user, data.pass);
      }
    } catch (e) {}
  }

  function startPairPolling(pin) {
    stopPairPolling();
    activePairPin = pin;
    checkPairStatus(pin);
    pairPollInterval = setInterval(() => checkPairStatus(pin), 400);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && activePairPin) {
      checkPairStatus(activePairPin);
    }
  });

  async function confirmPairing(pin, user, pass) {
    try {
      const res = await fetch("/pair/confirm", {
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

    // Se abriu no celular para parear uma TV (?pair=XXXX), esconde o QR code local
    const qrInlineWrap = document.querySelector(".login-qr-inline");
    if (pairPin && qrInlineWrap) {
      qrInlineWrap.style.display = "none";
      return;
    }

    if (!qrCodeImg || typeof qrcode === "undefined") return;
    // Gera PIN único de 4 dígitos para esta tela
    let pin = localStorage.getItem("nexus_tv_pin");
    if (!pin) {
      pin = String(Math.floor(1000 + Math.random() * 9000));
      localStorage.setItem("nexus_tv_pin", pin);
    }
    if (qrPinCode) qrPinCode.textContent = pin;

    // Gera o QR Code com a URL do pareamento
    try {
      const pairUrl = `https://play.nexusplay.tv/?pair=${pin}`;
      const qr = qrcode(0, "M");
      qr.addData(pairUrl);
      qr.make();
      qrCodeImg.src = qr.createDataURL(4, 2);
    } catch (e) {
      console.warn("Falha ao gerar QR Code:", e);
    }

    // A TV começa a escutar o pareamento imediatamente
    startPairPolling(pin);
  }

  initQrCode();

  // ---------------- Bootstrap: querystring / sessão salva ----------------
  function boot() {
    const params = new URLSearchParams(window.location.search);
    const walletToken = params.get("wallet");
    const qUser = params.get("user");
    const qPass = params.get("pass");
    const directUrl = params.get("url");
    const pairPin = params.get("pair");

    hideOverlay();

    // Se o celular abriu a página via QR Code escaneado da TV (?pair=XXXX):
    if (pairPin) {
      try {
        const saved = JSON.parse(localStorage.getItem("nexus_play_session") || "null");
        if (saved && saved.user && saved.pass) {
          showOverlay("Conectando sua TV…", `Enviando acesso para a Smart TV (PIN ${pairPin})…`);
          confirmPairing(pairPin, saved.user, saved.pass).then((res) => {
            if (res && res.success) {
              showOverlay("✅ TV Conectada!", "Sua Smart TV foi autorizada e já está dando o play!");
              setTimeout(() => {
                startSession(saved.user, saved.pass);
              }, 300);
            }
          });
          return;
        }
      } catch (e) {}

      // Se ainda não estava logado no celular, atualiza o botão para indicar a TV:
      if (els.btnLogin) {
        els.btnLogin.innerHTML = `Conectar TV (${pairPin}) <span aria-hidden="true">↗</span>`;
      }
    }

    if (directUrl && qUser && qPass) {
      startSession(qUser, qPass, { directUrl });
      return;
    }
    if (walletToken) {
      const creds = decodeWallet(walletToken);
      if (creds) { startSession(creds.user, creds.pass); return; }
      showLoginError("Token da carteira inválido ou expirado.");
    }
    if (qUser && qPass) { startSession(qUser, qPass); return; }

    updateFavBadge();

    // sessão local persistida (login manual anterior)
    try {
      const saved = JSON.parse(localStorage.getItem("nexus_play_session") || "null");
      if (saved && saved.user && saved.pass) {
        els.inUser.value = saved.user;
        startSession(saved.user, saved.pass);
        return;
      }
    } catch (e) {}

    setStatus("aguardando login", "");
  }

  boot();
})();
