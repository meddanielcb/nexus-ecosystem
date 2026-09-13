# RESPOSTA TÉCNICA E EVIDÊNCIAS DE INFRAESTRUTURA DOCKER & SUPERVISOR

> **Status:** Relatório técnico do agente residente no contêiner Docker (`hermes-gateway`).  
> **Data:** 13/09/2026  
> **Repositório:** `meddanielcb/nexus-ecosystem`  
> **Branch:** `infra/docker-supervisor-hardening`  
> **Auditoria:** Sem exposição de segredos, tokens ou dados reais de clientes.

---

## 1. Mapeamento do Entrypoint Real e Mecanismo de Inicialização do Supervisor

### 1.1 Cadeia de Processos Real (Inspeção ao Vivo)
A inspeção da árvore de processos (`ps -ef`, `cat /proc/<PID>/status`) comprovou a seguinte hierarquia estrita:
```text
PID 1: /usr/bin/tini -g -- /opt/hermes/docker/entrypoint.sh gateway (root)
 └─ PID 8: /opt/hermes/.venv/bin/python3 /opt/hermes/.venv/bin/hermes gateway (hermes)
     └─ PID 142139: /opt/hermes/.venv/bin/python3 /opt/data/digital_store_bot/supervisor.py (hermes)
         ├─ PID 142145: .../webhook_server.py
         ├─ PID 142146: .../run_store.py
         └─ PID 202648: /opt/hermes/.venv/bin/python3 /opt/data/nexus_playtv_bot/run_playtv.py
```

### 1.2 Como o Supervisor é Acionado
- O `entrypoint.sh` do contêiner executa `/opt/hermes/.venv/bin/hermes gateway` como PID 8.
- O gateway carrega o sistema de hooks em `/opt/data/hooks/autostart_nexus_store/`.
- O arquivo `HOOK.yaml` declara o evento `gateway:startup`.
- O script `handler.py` escuta esse evento e executa:
  `subprocess.Popen([python_bin, supervisor_script], cwd=..., start_new_session=True)`
- **Proteção contra Duplicidade:**
  O `supervisor.py` possui trava via abstract unix socket:
  `LOCK_SOCKET.bind('\0nexus_supervisor_lock')`
  Se outra instância for invocada, o socket impede a execução e encerra com exit code 0.
- **Limitação Identificada:** Se o gateway sofrer recriação completa sem o volume de hooks montado ou se o processo do gateway falhar sem encerrar o contêiner, o supervisor depende estritamente do loop de retry do hook. Uma unidade systemd gerenciada no host garante recuperação desacoplada do ciclo de vida do gateway.

---

## 2. Diagnóstico do Navegador Isolado e Sandbox

1. **Restrição no Contêiner (`hermes-gateway`):**
   - O contêiner roda sob Docker padrão sem permissões de `--privileged` nem `CAP_SYS_ADMIN`.
   - O Chromium com sandbox ativada exige unprivileged user namespaces (`CLONE_NEWUSER`), que falham com:
     `No usable sandbox! Update your kernel or see https://chromium.googlesource.com/...`
   - O teste com `--no-sandbox` contorna a inicialização interna, mas expõe vulnerabilidades e altera a assinatura de canvas/processo, facilitando a detecção por WAFs.
2. **Ambiente Recomendado no Host:**
   - Criação de contêiner dedicado e isolado (ex: `browser-sandbox`) ou serviço systemd exclusivo no host executado sob usuário dedicado sem privilégios (`browser-worker`).
   - Mapeamento estrito de interface loopback (`127.0.0.1:9222`) para a porta de depuração do Chrome DevTools Protocol (CDP), garantindo que ela permaneça inacessível externamente.

---

## 3. Desafio Anti-Bot na VPS: Diagnóstico da Falha e Requisitos da Emissão

### 3.1 Por Que o Turnstile Não Conclui no Datacenter
1. **Verificação de IP/ASN e Prova de Trabalho (PoW):**
   - No ambiente local (Mac), o Turnstile opera sob IP residencial/comercial leve, aceitando tokens passivos sem desafio interativo.
   - No IP da VPS Hostinger (`93.127.210.111`), o ASN de datacenter aciona o nível máximo de validação da Cloudflare, exigindo renderização interativa em iframe (`challenges.cloudflare.com`).
2. **Dependência de Sincronia de Estados no Frontend (React Hook Form):**
   - O botão `Entrar` do formulário web (`controle.vip/login`) possui `disabled="true"` atrelado ao estado interno do React Hook Form.
   - Mesmo resolvendo o token via serviço de captcha (2Captcha), o frontend só libera o envio se o valor for injetado no callback interno do Turnstile e os inputs de texto receberem eventos reais de `input`/`change` emitidos pelo DOM.

### 3.2 Descoberta Crítica: A Etapa de Criação de Linha (`userAdd`) Exige Google reCAPTCHA
A auditoria minuciosa no chunk de produção do painel (`https://controle.vip/assets/mutations-Ahp8ysrI.js`) revelou um fato crucial para a autonomia do sistema:
- A mutação de criação de usuários (`user:create-users`) executa:
  ```javascript
  const { adult_channels: w, is_trial: U, official_credits: v, ...d } = u;
  d["g-recaptcha-response"] = await e(U ? "userAddTrial" : "userAdd");
  ```
- **Conclusão Técnica:** Mesmo que o login seja resolvido e um JWT de 60 minutos seja emitido, **a criação de linha oficial (`POST /api/users`) e de testes (`POST /api/trial_users`) exige um token válido de Google reCAPTCHA v3 (`action: userAdd` / `userAddTrial`, Sitekey: `6LeJTpIeAAAAALiuQPGPcaXbs9XL-cKdwEBuOmJ7`)**.
- Qualquer chamada direta de backend sem o campo `g-recaptcha-response` válido é sumariamente rejeitada pela API `api.controle.fit`.

---

## 4. Recuperação de Processo Travado, Loops e Idempotência

### 4.1 Limitações Atuais do `supervisor.py`
- O supervisor atual verifica apenas se o processo encerrou (`p.poll() is not None`).
- Ele **não detecta travamentos silenciosos** (ex: processo bloqueado em I/O de rede ou deadlock de asyncio).

### 4.2 Arquitetura de Resiliência Proposta
1. **Heartbeat File / Socket:** Cada worker (`run_playtv`, `webhook_server`, `run_store`) deve atualizar um arquivo de timestamp a cada 30 segundos (ex: `/tmp/run_playtv.heartbeat`). Se o delta exceder 90 segundos, o supervisor encerra a árvore do processo com `SIGKILL` e reinicia.
2. **Backoff Exponencial:** Reinícios imediatos em loop geram bloqueio na API do Telegram (`429 Too Many Requests`). Implementar intervalo crescente: 5s → 15s → 30s → 60s (máximo).
3. **Fila Persistente e Idempotência:**
   - Webhook registra o pedido no SQLite com status `pending` antes de despachar.
   - Lock atômico por `order_id` evita corridas entre threads de entrega.
   - Em caso de timeout ao contatar o fornecedor, o status vai para `retry_pending` com re-tentativa após verificação de duplicidade (`GET /api/users?search=nx_<order_id>`).

---

## 5. Mapeamento de Configuração, Persistência e Segredos

### 5.1 Estado das Variáveis no Ambiente de Produção
Auditoria em `/opt/data/.env` e ambiente de processo:
- `STORE_BOT_TOKEN`: **PRESENTE** (Configurado no `.env` e exportado no ambiente).
- `PIXGET_API_KEY`: **PRESENTE** (Configurado no `.env`).
- `PIXGET_WEBHOOK_SECRET`: **PRESENTE** (Configurado no `.env`).
- `BLOCKBEE_API_KEY`: **PRESENTE** (Configurado no `.env`).
- `PLAYTV_BOT_TOKEN`: **PRESENTE NO PROCESSO** (Carregado na execução em memória de `run_playtv.py` e `webhook_server.py`; ausente no arquivo `.env` unificado).
- `ALERT_BOT_TOKEN`: **PRESENTE NO PROCESSO** (Carregado nos scripts `notifier.py`; ausente no `.env`).
- `P2BRAZ_USER` e `P2BRAZ_PASS`: **AUSENTES NO .ENV** (Armazenados isoladamente em arquivo local de chaves `/opt/data/nexus_playtv_bot/config_keys.json`).

### 5.2 Correções Efetuadas no Repositório (Sanitização)
- Todos os arquivos do repositório (`run_playtv.py`, `webhook_server.py`, `run_store.py`, `services.py`, `notifier.py`) foram refatorados para ler estritamente `os.getenv(...)`.
- **Todos os fallbacks contendo tokens ou hashes hardcoded foram eliminados do código do repositório.**
- O arquivo `.gitignore` protege estritamente bancos (`*.db`), arquivos `.env`, chaves (`config_keys.json`) e diretórios de cache.

### 5.3 Volumes e Persistência
- Volume Principal: `/opt/data` montado no contêiner a partir de `/opt/data` no host.
- Bancos de Dados SQLite:
  - `digital_store_bot/data/store.db`
  - `nexus_playtv_bot/data/playtv.db`
  - Backup diário recomendado: Snapshot diário via script local compactando `*.db` para `/opt/data/backups/`.

---

## 6. Lista Exata de Alterações Efetuadas e Rollback

### Alterações Efetuadas:
1. Criação do arquivo de documentação técnica: `docs/RESPOSTA_AGENTE_DOCKER.md`.
2. Sanitização de credenciais nos códigos de `nexus_repo` (remoção de fallbacks hardcoded de tokens nas chamadas de bot e serviços).
3. Criação e checkout da branch isolada: `infra/docker-supervisor-hardening`.
4. **Zero impacto em produção:** Nenhum serviço em execução no contêiner ou host foi reiniciado, finalizado ou alterado.

### Como Reverter:
Caso deseje descartar as alterações da branch:
```bash
git -C /opt/data/nexus_repo checkout main
git -C /opt/data/nexus_repo branch -D infra/docker-supervisor-hardening
```
