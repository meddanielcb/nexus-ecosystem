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
    btnToggleList: document.getElementById("btnToggleList"),
    sidebar: document.getElementById("sidebar"),
  };

  let hls = null;
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
      // já é same-origin (ex: segmentos relativos que o hls.js resolveu)
      if (u.origin === window.location.origin) return u.pathname + u.search;
      // upstream real -> troca para o proxy same-origin
      return PROXY_BASE + u.pathname + u.search;
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

  // ---------------- Player HLS ----------------
  function destroyHls() {
    if (hls) { try { hls.destroy(); } catch (e) {} hls = null; }
  }

  function playStream(streamUrl, label) {
    destroyHls();
    showOverlay("Carregando stream…", label || "");
    setStatus("carregando", "");

    const video = els.video;
    const finalUrl = toProxied(streamUrl);

    if (window.Hls && window.Hls.isSupported()) {
      hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 60,
        maxBufferLength: 30,
        enableWorker: true,
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
            destroyHls();
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
      showOverlay("Navegador incompatível", "Seu navegador não suporta reprodução HLS.");
      setStatus("indisponível", "err");
    }
  }

  // ---------------- Lista de canais ----------------
  function renderChannelList(streams) {
    const q = (els.searchInput.value || "").toLowerCase().trim();
    const cat = els.catSelect.value;
    const filtered = streams.filter(s => {
      if (cat && String(s.category_id) !== String(cat)) return false;
      if (q && !String(s.name || "").toLowerCase().includes(q)) return false;
      return true;
    });

    if (!filtered.length) {
      els.channelList.innerHTML = `<div class="empty-hint">Nenhum canal encontrado.</div>`;
      return;
    }

    els.channelList.innerHTML = filtered.slice(0, 400).map(s => {
      const logo = s.stream_icon ? toProxied(s.stream_icon) : "";
      const active = String(s.stream_id) === String(activeStreamId) ? " active" : "";
      return `<div class="chan${active}" data-id="${s.stream_id}">
        ${logo ? `<img class="logo" src="${logo}" loading="lazy" onerror="this.style.visibility='hidden'">` : `<div class="logo"></div>`}
        <span class="name">${(s.name || "Canal").replace(/</g, "&lt;")}</span>
      </div>`;
    }).join("");

    els.channelList.querySelectorAll(".chan").forEach(el => {
      el.addEventListener("click", () => {
        const id = el.getAttribute("data-id");
        const stream = streams.find(s => String(s.stream_id) === String(id));
        if (!stream) return;
        activeStreamId = id;
        els.npChannel.textContent = stream.name || "Canal";
        renderChannelList(streams);
        if (window.innerWidth <= 860) els.sidebar.classList.remove("open");
        playStream(buildLiveUrl(session.user, session.pass, stream.stream_id), stream.name);
      });
    });
  }

  function renderCategories(cats) {
    els.catSelect.innerHTML = `<option value="">Todas as categorias</option>` +
      cats.map(c => `<option value="${c.category_id}">${(c.category_name || "").replace(/</g, "&lt;")}</option>`).join("");
  }

  // ---------------- Fluxo de sessão ----------------
  async function startSession(user, pass, opts) {
    opts = opts || {};
    els.gate.classList.add("hidden");
    showOverlay("Autenticando…", `Validando ${user} no servidor de streaming.`);
    setStatus("autenticando", "");
    try {
      const login = await xtreamLogin(user, pass);
      session = { user, pass };
      localStorage.setItem("nexus_play_session", JSON.stringify(session));

      els.npUser.textContent = `Conta: ${user}${login.user_info && login.user_info.exp_date ? " • expira " + new Date(login.user_info.exp_date * 1000).toLocaleDateString("pt-BR") : ""}`;
      els.btnToggleList.style.display = "inline-flex";

      showOverlay("Carregando canais…", "Montando sua lista de canais ao vivo.");
      const [streams, cats] = await Promise.all([
        fetchLiveStreams(user, pass).catch(() => []),
        fetchCategories(user, pass).catch(() => []),
      ]);
      allStreams = Array.isArray(streams) ? streams : [];
      renderCategories(Array.isArray(cats) ? cats : []);
      renderChannelList(allStreams);

      if (opts.directUrl) {
        playStream(opts.directUrl, "Stream direto");
      } else if (allStreams.length) {
        const first = allStreams[0];
        activeStreamId = first.stream_id;
        els.npChannel.textContent = first.name || "Canal";
        renderChannelList(allStreams);
        playStream(buildLiveUrl(user, pass, first.stream_id), first.name);
      } else {
        hideOverlay();
        setStatus("conectado", "live");
      }
    } catch (err) {
      console.error(err);
      els.gate.classList.remove("hidden");
      showLoginError(err.message || "Falha ao autenticar.");
      setStatus("erro de login", "err");
      hideOverlay();
    }
  }

  function logout() {
    destroyHls();
    localStorage.removeItem("nexus_play_session");
    session = null;
    activeStreamId = null;
    els.video.removeAttribute("src");
    els.npChannel.textContent = "Nenhum canal selecionado";
    els.npUser.textContent = "";
    els.channelList.innerHTML = `<div class="empty-hint">Faça login para carregar a lista de canais.</div>`;
    els.btnToggleList.style.display = "none";
    els.gate.classList.remove("hidden");
    setStatus("desconectado", "");
    hideOverlay();
  }

  // ---------------- Eventos de UI ----------------
  els.btnLogin.addEventListener("click", () => {
    const user = els.inUser.value.trim();
    const pass = els.inPass.value;
    els.loginErr.style.display = "none";
    if (!user || !pass) { showLoginError("Informe usuário e senha."); return; }
    startSession(user, pass);
  });
  [els.inUser, els.inPass].forEach(inp => inp.addEventListener("keydown", e => {
    if (e.key === "Enter") els.btnLogin.click();
  }));
  els.btnLogout.addEventListener("click", logout);
  els.btnReload.addEventListener("click", () => {
    if (session && activeStreamId) playStream(buildLiveUrl(session.user, session.pass, activeStreamId), els.npChannel.textContent);
  });
  els.btnFullscreen.addEventListener("click", () => {
    const wrap = els.video.closest(".player-wrap");
    if (wrap.requestFullscreen) wrap.requestFullscreen();
    else if (els.video.webkitEnterFullscreen) els.video.webkitEnterFullscreen();
  });
  els.btnToggleList.addEventListener("click", () => els.sidebar.classList.toggle("open"));
  els.searchInput.addEventListener("input", () => renderChannelList(allStreams));
  els.catSelect.addEventListener("change", () => renderChannelList(allStreams));

  // ---------------- Bootstrap: querystring / sessão salva ----------------
  function boot() {
    const params = new URLSearchParams(window.location.search);
    const walletToken = params.get("wallet");
    const qUser = params.get("user");
    const qPass = params.get("pass");
    const directUrl = params.get("url");

    hideOverlay();

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
