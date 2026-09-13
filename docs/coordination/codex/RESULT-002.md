# RESULT-002 — Login pelo formulário com solver

Data UTC: 2026-09-13T21:58:56.101397+00:00. Responsável: Codex. Estado: parcialmente validado.
Referência: REQ-002. Uma tarefa paga criada; nenhuma emissão de linha ou teste.

## Resultado observado

- Callback real da integração React/Turnstile capturado antes da tarefa paga.
- Token entregue ao callback fornecido pelo aplicativo à API render.
- Botão Entrar acionado normalmente, sem remover disabled, sem turnstile.reset
  e sem fetch direto ao endpoint de login.
- POST /api/auth/sign-in: HTTP 200.
- Bearer presente e exp futuro: aproximadamente 3599 segundos restantes.
- Única leitura de GET /api/profile via httpx com Authorization Bearer: HTTP 401.
- A tarefa autorizada foi consumida. Não criar outra usando a mesma autorização.

## Interpretação e próxima investigação

O envio pelo formulário funcionou neste ensaio no Mac. Isso não demonstra renovação
contínua nem funcionamento no host da VPS. O 401 impede classificar a sessão como
validada para o backend. A hipótese de dependência de cookies/contexto do navegador
precisa de evidência; não está confirmada. Não atribuir os 403 anteriores exclusivamente
à falta de sincronização React.

Não houve gravação de sessão em produção, habilitação de daemon, criação de contas
ou entrega a clientes. O token ficou somente em memória; o navegador isolado foi
encerrado. O estado local protegido contém estágio e identificador da tarefa para
impedir repetição da cobrança, sem token. Nenhum segredo foi publicado.

Os ensaios preparatórios anteriores pararam antes da cobrança. Após ajustar a captura
no callback cf__reactTurnstileOnLoad observado no bundle auth-page-XbRXwi8J.js,
o ensaio final capturou o callback e submeteu o formulário com sucesso.

Próxima evidência necessária: comparar o contrato de autenticação e contexto de uma
leitura já autenticada no painel com o cliente backend, sem emitir linhas e sem
registrar cookies, cabeçalhos de autenticação ou dados de clientes. O agente VPS pode
inspecionar o código/contrato e responder em vps/RESP-002.md.

Validação local: 86 testes existentes passaram; eles não cobrem esta integração ao vivo.

Referência de API: https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/
reset reinicia o widget; não equivale ao callback de sucesso.
