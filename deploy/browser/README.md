# Navegador persistente do fornecedor no host

Unidade específica para a VPS Ubuntu já inspecionada: `nexus-supplier-browser.service`.
Executa Chrome + Xvfb como usuário existente `ubuntu`, com sandbox padrão e
perfil em `/var/lib/nexus-supplier-browser/profile` (diretório de estado 0700,
umask 0077). Não usa o perfil pessoal do fundador.

CDP deve escutar exclusivamente em `127.0.0.1:9222`. Não publicar essa porta via
Caddy, Docker ou firewall. O consumidor precisa executar no host ou usar um canal
local controlado; o localhost do contêiner não é o localhost do host.

O consumidor conecta ao contexto padrão já existente via CDP. Não usar
`browser.new_context()` para a sessão de produção nem `browser.close()` ao
terminar uma consulta; desconectar o cliente preserva o processo gerenciado.

Persistência do perfil não garante renovação do JWT nem restauração de estado
que o site mantenha somente em memória. Validar login por operação autenticada,
nunca pela existência de cookies, porta aberta ou status systemd ativo.

Restart=always recupera encerramento do processo; não detecta congelamento por
si só. O limite de reinícios evita loop e pode deixar a unidade em falha até
intervenção. Watchdog de atividade ainda precisa de implementação/homologação.
Saída do Chrome foi desabilitada para evitar logs com dados sensíveis.

Verificação operacional:

```sh
systemctl is-active nexus-supplier-browser.service
systemctl is-enabled nexus-supplier-browser.service
ss -ltnp '( sport = :9222 )'
```

Rollback, se necessário: `systemctl disable --now nexus-supplier-browser.service`.
Preservar o perfil; contém autenticação sensível e não deve entrar no Git ou em
backups sem proteção apropriada. Não tocar nos bots existentes para este rollback.
