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
      const finalLogo = logo || "/favicon.png";
      return `<div class="chan${active}" data-id="${s.stream_id}">
        <img class="logo" src="${finalLogo}" loading="lazy" onerror="this.onerror=null;this.src='/favicon.png';">
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
        playStream(stream.stream_id, stream.name);
      });
    });
  }

  // Dropdown Customizado de Categorias (Renderizado diretamente na interface)
  const catDropdown = document.getElementById("customCatDropdown");
  const catTrigger = document.getElementById("catDropdownTrigger");
  const catMenu = document.getElementById("catDropdownMenu");
  const catLabel = document.getElementById("catCurrentLabel");

  function toggleCatDropdown(open) {
    if (!catDropdown) return;
    const isOpen = open !== undefined ? open : !catDropdown.classList.contains("open");
    catDropdown.classList.toggle("open", isOpen);
    if (catTrigger) catTrigger.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }

  if (catTrigger) {
    catTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleCatDropdown();
      resetAutoRetractTimer();
    });
  }

  document.addEventListener("click", (e) => {
    if (catDropdown && !catDropdown.contains(e.target)) {
      toggleCatDropdown(false);
    }
  });

  function renderCategories(cats) {
    els.catSelect.innerHTML = `<option value="">Todas as categorias</option>` +
      cats.map(c => `<option value="${c.category_id}">${(c.category_name || "").replace(/</g, "&lt;")}</option>`).join("");

    if (catMenu) {
      catMenu.innerHTML = `<div class="cat-item active" data-id="">Todas as categorias</div>` +
        cats.map(c => `<div class="cat-item" data-id="${c.category_id}">${(c.category_name || "").replace(/</g, "&lt;")}</div>`).join("");

      catMenu.querySelectorAll(".cat-item").forEach(item => {
        item.addEventListener("click", (e) => {
          e.stopPropagation();
          const id = item.getAttribute("data-id");
          els.catSelect.value = id;
          catMenu.querySelectorAll(".cat-item").forEach(i => i.classList.remove("active"));
          item.classList.add("active");
          if (catLabel) catLabel.textContent = item.textContent;
          toggleCatDropdown(false);
          renderChannelList(allStreams);
          resetAutoRetractTimer();
        });
      });
    }
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

      showOverlay("Carregando canais…", "Montando sua lista de canais ao vivo.");
      const [streams, cats] = await Promise.all([
        fetchLiveStreams(user, pass).catch(() => []),
        fetchCategories(user, pass).catch(() => []),
      ]);
      allStreams = Array.isArray(streams) ? streams : [];
      renderCategories(Array.isArray(cats) ? cats : []);
      renderChannelList(allStreams);

      if (opts.directUrl) {
        fallbackHls(opts.directUrl, "Stream direto");
      } else if (allStreams.length) {
        const first = allStreams[0];
        activeStreamId = first.stream_id;
        els.npChannel.textContent = first.name || "Canal";
        renderChannelList(allStreams);
        playStream(first.stream_id, first.name);
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
    destroyPlayer();
    localStorage.removeItem("nexus_play_session");
    session = null;
    activeStreamId = null;
    els.video.removeAttribute("src");
    els.npChannel.textContent = "Nenhum canal selecionado";
    els.npUser.textContent = "";
    els.channelList.innerHTML = `<div class="empty-hint">Faça login para carregar a lista de canais.</div>`;
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
  els.btnFullscreen.addEventListener("click", () => {
    const wrap = els.video.closest(".player-wrap");
    if (wrap.requestFullscreen) wrap.requestFullscreen();
    else if (els.video.webkitEnterFullscreen) els.video.webkitEnterFullscreen();
  });
  els.searchInput.addEventListener("input", () => renderChannelList(allStreams));
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

  // Aciona automaticamente o Lower-Third a cada 2.5 minutos se o vídeo estiver tocando
  setInterval(() => {
    if (els.video && !els.video.paused && els.video.currentTime > 5) {
      showLowerThird(10000);
    }
  }, 150000);

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
    // Se a lista estiver EXPANDIDA (não tem channels-retracted)
    if (sidebar && !sidebar.classList.contains("channels-retracted")) {
      autoRetractTimer = setTimeout(() => {
        // Não recolhe se o dropdown de categorias ainda estiver aberto
        if (catDropdown && catDropdown.classList.contains("open")) {
          resetAutoRetractTimer();
          return;
        }
        sidebar.classList.add("channels-retracted");
        if (btnToggleChannels) {
          btnToggleChannels.setAttribute("aria-expanded", "false");
          btnToggleChannels.title = "Expandir lista de canais";
        }
      }, 2000); // 2 segundos sem interação
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

  // ---------------- Sistema de Login Smart TV / QR Code ----------------
  const tabQr = document.getElementById("tabQr");
  const tabForm = document.getElementById("tabForm");
  const paneQr = document.getElementById("paneQr");
  const paneForm = document.getElementById("paneForm");
  const qrCodeImg = document.getElementById("qrCodeImg");
  const qrPinCode = document.getElementById("qrPinCode");

  function switchLoginTab(mode) {
    if (!tabQr || !tabForm || !paneQr || !paneForm) return;
    if (mode === "qr") {
      tabQr.classList.add("active");
      tabForm.classList.remove("active");
      paneQr.classList.add("active");
      paneForm.classList.remove("active");
    } else {
      tabForm.classList.add("active");
      tabQr.classList.remove("active");
      paneForm.classList.add("active");
      paneQr.classList.remove("active");
      if (els.inUser) els.inUser.focus();
    }
  }

  if (tabQr && tabForm) {
    tabQr.addEventListener("click", () => switchLoginTab("qr"));
    tabForm.addEventListener("click", () => switchLoginTab("form"));
  }

  function initQrCode() {
    if (!qrCodeImg || typeof qrcode === "undefined") return;
    // Gera ou recupera PIN de 4 dígitos para esta TV
    let pin = localStorage.getItem("nexus_tv_pin");
    if (!pin) {
      pin = String(Math.floor(1000 + Math.random() * 9000));
      localStorage.setItem("nexus_tv_pin", pin);
    }
    if (qrPinCode) qrPinCode.textContent = pin;

    // Gera o QR Code com alta densidade
    try {
      const pairUrl = `https://play.nexusplay.tv/?pair=${pin}`;
      const qr = qrcode(0, "M");
      qr.addData(pairUrl);
      qr.make();
      qrCodeImg.src = qr.createDataURL(6, 2);
    } catch (e) {
      console.warn("Falha ao gerar QR Code:", e);
    }
  }

  initQrCode();

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
