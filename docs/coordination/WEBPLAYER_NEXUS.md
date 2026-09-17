# WebPlayer Proprietário Nexus — `play.nexusplay.tv`

> **Status:** Em produção.
> **Responsável:** Subagente 3 (Infraestrutura/Arquitetura VPS).
> **Data:** 17/09/2026 (UTC).
> **Infra:** VPS Njalla `45.158.116.180` (Ubuntu 24.04, Nginx 1.24.0).

## 1. Objetivo

Servir um WebPlayer HTML/JS leve, próprio da Nexus, em `https://play.nexusplay.tv`,
capaz de reproduzir os streams Xtream Codes do fornecedor (`http://atmt.space`)
dentro do navegador **sem erro de Mixed Content e sem erro de CORS**, através
de um proxy reverso same-origin no Nginx.

## 2. Problema resolvido

- O fornecedor de streaming (`atmt.space`) só responde em **HTTP puro**
  (Xtream Codes clássico: `player_api.php`, `get.php`, `/live/user/pass/id.m3u8`).
- O WebPlayer roda em **HTTPS** (`play.nexusplay.tv`, cert Let's Encrypt).
- Browsers modernos bloqueiam:
  - **Mixed Content**: página HTTPS não pode carregar recursos ativos (XHR/fetch/vídeo) via HTTP.
  - **CORS**: `atmt.space` não teria motivo para liberar `Access-Control-Allow-Origin`
    para `play.nexusplay.tv`.
- **Solução:** todo tráfego de API e mídia passa por `https://play.nexusplay.tv/stream/…`,
  que o Nginx repassa internamente (server-to-server, HTTP puro, sem exposição no
  browser) para `http://atmt.space/…`, injetando os headers CORS na resposta.
  O browser nunca fala diretamente com `atmt.space`.

## 3. Arquitetura

```
┌──────────────┐   HTTPS (same-origin)   ┌─────────────────────────────┐   HTTP puro   ┌───────────────┐
│  Navegador   │ ───────────────────────▶ │ Nginx @ play.nexusplay.tv  │ ─────────────▶ │ atmt.space     │
│ (WebPlayer)  │ ◀─────────────────────── │ + headers CORS injetados   │ ◀───────────── │ (Xtream Codes) │
└──────────────┘   /  e  /stream/*        └─────────────────────────────┘                └───────────────┘
```

- `GET https://play.nexusplay.tv/`         → arquivos estáticos do WebPlayer (`index.html`, `app.js`, `favicon.png`).
- `GET https://play.nexusplay.tv/stream/*` → proxy transparente para `http://atmt.space/*`
  (mesma URI, sem prefixo `/stream/` no upstream).

## 4. Arquivos em produção (VPS)

| Caminho na VPS | Conteúdo | Origem local |
|---|---|---|
| `/var/www/play.nexusplay.tv/index.html` | Markup + CSS do player (dark, preto + ciano `#00E5FF` + verde neon `#39FF88`) | `/opt/data/webplayer_build/index.html` |
| `/var/www/play.nexusplay.tv/app.js` | Lógica do player: login, wallet token, chamadas Xtream, HLS.js, lista de canais | `/opt/data/webplayer_build/app.js` |
| `/var/www/play.nexusplay.tv/favicon.png` | Ícone (do brand kit Nexus) | `nexus-icon-192.png` |
| `/etc/nginx/conf.d/play.nexusplay.tv.conf` | vhost 80→443 redirect + location `/` + location `/stream/` (proxy CORS) | `/opt/data/webplayer_build/play.nexusplay.tv.conf` |

TLS: reaproveita o certificado wildcard-multi-SAN já emitido em
`/etc/letsencrypt/live/nexusplay.tv/fullchain.pem`
(domínios: `nexusplay.tv, www.nexusplay.tv, api.nexusplay.tv, play.nexusplay.tv`).

## 5. Configuração Nginx (proxy anti-CORS/Mixed Content)

Bloco relevante (arquivo completo em `/etc/nginx/conf.d/play.nexusplay.tv.conf`):

```nginx
location /stream/ {
    if ($request_method = OPTIONS) {
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
        add_header Access-Control-Allow-Headers "*" always;
        add_header Access-Control-Max-Age 86400 always;
        add_header Content-Length 0;
        return 204;
    }

    proxy_pass http://atmt.space/;   # upstream LITERAL — ver nota abaixo
    proxy_http_version 1.1;
    proxy_set_header Host atmt.space;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";

    proxy_buffering off;            # streaming HLS/TS suave, sem lag de buffer
    proxy_request_buffering off;
    proxy_cache off;
    proxy_redirect off;
    proxy_hide_header Set-Cookie;   # nunca expõe cookie do upstream ao browser
    add_header X-Accel-Buffering "no" always;

    add_header Access-Control-Allow-Origin "*" always;
    add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
    add_header Access-Control-Allow-Headers "*" always;
    add_header Access-Control-Expose-Headers "*" always;
    add_header Cross-Origin-Resource-Policy "cross-origin" always;
}
```

### ⚠️ Armadilha do Nginx encontrada e corrigida durante o deploy

A primeira versão usava `proxy_pass http://$upstream_var/;` (variável) pensando
em permitir re-resolução de DNS caso o IP do Cloudflare por trás de `atmt.space`
mudasse. **Isso quebra a decapagem do prefixo `/stream/`**: quando o destino do
`proxy_pass` é montado com variável, o Nginx deixa de remover o prefixo do
`location` e repassa a URI completa (`/stream/player_api.php`) ao upstream — que
não tem essa rota e cai no fallback SPA do painel (`atmt.space` devolvia o HTML
do React em vez do JSON da API). Corrigido usando `proxy_pass http://atmt.space/;`
**literal** (decapagem correta de `/stream/xxx` → `/xxx`). Trade-off aceito:
DNS é resolvido na carga/reload do Nginx; um `systemctl reload nginx` re-resolve
se o IP mudar (IPs Cloudflare são estáveis na prática).

## 6. WebPlayer (frontend)

- **Stack:** HTML + CSS + JS puro (sem framework/build step) + **HLS.js 1.5.15** via CDN
  (`jsdelivr`), com fallback para HLS nativo no Safari/iOS
  (`video.canPlayType('application/vnd.apple.mpegurl')`).
- **Visual:** dark theme (`#070A0D` fundo), destaque ciano `#00E5FF` e verde neon `#39FF88`,
  responsivo (sidebar de canais colapsa em mobile), cartão de login com o
  padrão visual já usado nos cartões VIP do bot (`acesso_vip.html`).
- **Fluxo de autenticação (3 modos, resolvidos em `app.js › boot()`):**
  1. **Login manual:** formulário usuário/senha → `POST` (via `fetch` GET real do
     Xtream) para `/stream/player_api.php?username=...&password=...`.
  2. **Login automático via `?user=...&pass=...`** na URL (ex.: link enviado
     pelo bot após pagamento).
  3. **Login automático via `?wallet=<token>`** — token da carteira, decodificado
     no cliente (`decodeWallet()`), aceita dois formatos:
     - `base64url(JSON)` → `{"user":"...","pass":"...","exp": <unix opcional>}`
     - `base64url("user:pass")`
     Exemplo gerado para o teste desta implantação:
     ```
     https://play.nexusplay.tv/?wallet=eyJ1c2VyIjogInRlc3RlX3dhbGxldCIsICJwYXNzIjogInNlbmhhX3dhbGxldCJ9
     ```
     (decodifica para `{"user":"teste_wallet","pass":"senha_wallet"}`)
  4. Também aceita `?url=<stream_direto>&user=X&pass=Y` para apontar direto a
     uma URL de mídia (bypassa a listagem de canais).
  - Sessão válida é persistida em `localStorage` (`nexus_play_session`) para
    reentrada automática sem novo login.
- **Depois do login:** busca `get_live_categories` e `get_live_streams` via
  Xtream API (proxied), monta lista de canais com busca/filtro por categoria,
  e inicia o primeiro canal automaticamente. Trocar de canal monta a URL
  `/stream/live/<user>/<pass>/<id>.m3u8` e recarrega o HLS.js.
- **Todas as URLs absolutas do upstream (`http://atmt.space/...`), incluindo
  logos de canal e segmentos `.ts`, são reescritas no cliente (`toProxied()`)
  para o caminho relativo `/stream/...`** antes de qualquer uso — garante que
  nada no player tente falar diretamente com `atmt.space` em HTTP.

## 7. Testes executados (evidência real, 17/09/2026)

```bash
# 1) Player estático
curl -sI https://play.nexusplay.tv/        # HTTP/2 200, sem -k (cert válido)
curl -sI https://play.nexusplay.tv/app.js  # HTTP/2 200

# 2) Proxy Xtream via HTTPS same-origin (credenciais de teste inválidas de propósito)
curl -s "https://play.nexusplay.tv/stream/player_api.php?username=teste&password=teste"
# -> {"user_info":null,"server_info":{"url":"atmt.space","port":"80", ...}}  (401, JSON real do fornecedor)

# 3) Preflight CORS
curl -sI -X OPTIONS "https://play.nexusplay.tv/stream/player_api.php"
# -> HTTP/2 204, access-control-allow-origin: *, access-control-allow-methods: GET, HEAD, OPTIONS

# 4) Certificado
openssl s_client -connect play.nexusplay.tv:443 -servername play.nexusplay.tv | openssl x509 -noout -subject -dates
# -> subject=CN=nexusplay.tv | válido até 15/12/2026
```

**Teste end-to-end em navegador real (Chromium via CDP):**
Abrindo `https://play.nexusplay.tv/?wallet=eyJ1c2VyIjogInRlc3RlX3dhbGxldCIsICJwYXNzIjogInNlbmhhX3dhbGxldCJ9`:
- Token da carteira decodificado corretamente (`teste_wallet` / `senha_wallet`).
- Login automático disparado sem interação do usuário.
- `fetch` foi para `/stream/player_api.php` (same-origin, HTTPS) — **nenhum erro
  de CORS/Mixed Content** (senão o `fetch` teria lançado `TypeError: Failed to fetch`).
- Resposta real do fornecedor (`401`, credenciais de teste inválidas) foi
  recebida e tratada corretamente pela UI: `"HTTP 401 ao autenticar"` exibido
  no cartão de login, status pill em `"erro de login"`.
- Conclusão: pipeline de proxy + player está correto; falta apenas testar com
  uma credencial Xtream real e válida (ex.: uma linha de teste gerada pelo bot)
  para validar a reprodução de vídeo H.264/HLS de ponta a ponta — isso não foi
  feito aqui pois nenhuma credencial válida foi fornecida a este subagente.

## 8. Pendências / próximos passos sugeridos

- [ ] Validar reprodução real de um canal ao vivo com uma linha Xtream válida
      (gerar teste via `nexus_playtv_bot/masterx_api.py::create_masterx_line`)
      e confirmar handshake HLS.js completo (`MANIFEST_PARSED` → vídeo tocando).
- [ ] Decidir/implementar quem **emite** o `?wallet=` token (bot Telegram / API
      de checkout) — o WebPlayer só **consome** o formato documentado na seção 6.
      Se o emissor assinar o token (HMAC) além de codificar, adicionar verificação
      de assinatura em `app.js` antes de usar as credenciais.
- [ ] Adicionar suporte a VOD/Séries (`get_vod_streams`, `get_series`) — hoje o
      player só lista/reproduz canais ao vivo (`get_live_streams`).
  Este proxy também repassa outras rotas Xtream automaticamente (`movie/`,
  `series/`, `xmltv.php`), então o backend já está pronto — falta só a UI.
- [ ] Monitorar se `atmt.space` muda de IP atrás do Cloudflare; se a
      resolução do Nginx ficar obsoleta, `systemctl reload nginx` resolve
      (nenhum downtime de config foi observado durante os testes).
