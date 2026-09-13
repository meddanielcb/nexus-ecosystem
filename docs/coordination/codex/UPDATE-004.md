# UPDATE-004 — Navegador persistente instalado no host

Data: 2026-09-13. Responsável: Codex. Pedido direto de Daniel: manter navegador
na VPS e validar leitura no mesmo contexto. Serviço instalado nesta etapa.

- Unidade: /etc/systemd/system/nexus-supplier-browser.service
- Estado observado: active/running, enabled, NRestarts=0.
- Chrome + Xvfb executados como ubuntu, sandbox padrão preservada.
- Perfil: /var/lib/nexus-supplier-browser/profile; estado e perfil com modo 0700.
- CDP observado somente em 127.0.0.1:9222, PID Chrome observado 717083.
- Restart=always, RestartSec=15, limite de 5 inicializações/300 segundos.
- Não houve reinício de bots ou contêineres existentes.

Login normal no contexto padrão persistente: credenciais preenchidas, espera de
60 segundos, botão bloqueado por desafio. Resultado: login_page=true,
responses=[], challenge_pending=true. NÃO há sessão autenticada validada.
Navegador foi deixado aberto e não deve ser fechado pelo cliente CDP.

Transferência de credenciais cifrada com RSA-OAEP/SHA256; chave privada temporária
removida, conforme verificação. Arquivo login-check.py contém apenas código e
texto cifrado, sem credenciais em claro. Não publicar o perfil nem seus arquivos.

O Codex solicitou autorização para UMA nova tarefa 2Captcha neste navegador da
VPS. Autorização anterior foi consumida no Mac. Não executar solver em paralelo
nem tratar este relatório como autorização de gasto. Script de ensaio persistente
foi preparado localmente; ainda não foi transferido/executado no host.

Limites: boot real e recuperação de travamento não foram ensaiados. Configuração
de reinício não é prova de recuperação. JWT não é renovado por manter Chrome aberto.
O próprio watchdog de aplicação e o consumo desse contexto pelo bot seguem pendentes.

Rollback restrito ao novo serviço: systemctl disable --now nexus-supplier-browser.service.
Preservar o perfil protegido e os bots existentes. A unidade versionável está no
workspace Codex em deploy/browser/nexus-supplier-browser.service.
