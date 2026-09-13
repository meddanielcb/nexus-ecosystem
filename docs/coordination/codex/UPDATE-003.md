# Adaptação do modelo de sessão persistente — 13/09/2026

Implementação local, sem deploy nem novo gasto em captcha.

- CaptchaBudget: SQLite, reserva transacional antes da chamada paga, limite em janela
  móvel de 24 horas, tarefas conhecidas registradas e resultado incerto mantém reserva.
- Backoff de falhas de autenticação e circuito persistentes. Reinício e meia-noite
  não apagam o bloqueio. Sucesso não apaga o consumo já reservado.
- CaptchaService aceita o orçamento; o ensaio UI passa a usá-lo com limite de uma
  tarefa por 24 horas compartilhado no diretório protegido. Flag de autorização
  e arquivo de tentativa continuam exigidos. O limite não concede autorização.
- SupplierReadClient não renova em 401 por padrão; distingue 403, 429 e 5xx sem
  presumir que signifiquem conta sem plano ou sessão expirada.
- Comparador de perfil preparado para navegador com cookies e HTTP com Bearer;
  exige token existente não expirado e não faz login. Retorna somente status,
  não cookies, tokens ou dados de cliente. Ainda não executado ao vivo.

Validação: 97 testes locais passaram, incluindo concorrência, reinício, resultado
incerto na criação, limite persistente, circuito atravessando meia-noite e erros
sem exposição de credenciais. Não comprovam o fluxo em produção.

Limitações: limite é de quantidade de tarefas, não valor monetário; custo real e
saldo ainda não são reconciliados. Orçamento só protege chamadores que o fornecem;
o ensaio UI foi integrado, scripts diagnósticos antigos não devem ser usados como
serviço de produção. Os limites atuais são do ensaio, não dimensionamento comercial.
O histórico de tarefas anteriores não foi importado para o novo ledger.
A sessão ainda não tem persistência homologada nem renovação validada; o último
resultado ao vivo continua sign-in 200 e perfil HTTP separado 401. Não habilitar
produção nem redefinir o circuito só porque o login ou solver respondeu 200.

Próxima etapa: diagnóstico com sessão já válida, sem comprar outro captcha,
comparando contrato e contexto. Preparar adaptação do processo proprietário da
sessão e testar reinício antes de integrar a emissão de linhas pagas.

Código permanece no workspace Codex, ainda não publicado para a VPS.
