# Revisão do handoff de infraestrutura — 13/09/2026

Referência auditada: `infra/docker-supervisor-hardening`, commit
`3e5b6b0eb6f9eaae4f598f9cfcc3205c4c79b6a3`.
O relatório original foi preservado em `RESPOSTA_AGENTE_DOCKER.md`.
Não houve merge, implantação, reinício ou emissão de linha nesta revisão.

## Resultado

O commit altera sete arquivos Python para remover credenciais literais e adiciona
o relatório. Não altera o supervisor, o hook de inicialização nem instala um
serviço de navegador. Heartbeat, backoff e recuperação são propostas, não entregas
implementadas nesse commit. A remoção de segredos é útil, mas não basta para
aprovar a publicação.

## Correções necessárias antes de incorporar

1. **Segredo Pixget ausente:** na versão desse commit, `webhook_server.py:345`
   usa `os.getenv("PIXGET_WEBHOOK_SECRET", "")`; a linha 348 calcula HMAC
   mesmo com a chave vazia e a linha 352 compara a assinatura. Nesse estado de
   configuração, terceiros podem calcular uma assinatura aceita. A implementação
   local em `payment_inbox.authenticate` já recusa segredo vazio; preservar essa
   proteção. A presença atual do segredo na VPS não elimina a falha de configuração.
2. **Variáveis após reinício:** tokens carregados em variáveis Python não comprovam
   que existam no ambiente herdado por novos processos. O próprio relatório indica
   PLAYTV_BOT_TOKEN e ALERT_BOT_TOKEN ausentes do `.env`. Antes da migração,
   verificar apenas presença e não-vazio no ambiente efetivo de cada serviço,
   sem imprimir valores. Configuração obrigatória ausente deve impedir startup.
3. **Reconciliação:** o painel observado usa `text_search`, não `search`.
   Preservar a consulta local com paginação e igualdade exata do nome determinístico.
   Resultado vazio não autoriza repetir automaticamente uma criação cujo resultado
   ficou incerto; a requisição anterior pode ter sido aceita pelo fornecedor.
4. **Backup:** não compactar simplesmente bancos SQLite ativos. Usar a API de
   backup do SQLite ou snapshot consistente incluindo o estado WAL, e testar
   restauração. A existência de um arquivo de backup não prova recuperação.
5. **Rollback:** `git checkout main` muda o checkout, não restaura processos,
   configuração ou bancos em execução. Registrar versão implantada, configuração,
   compatibilidade das migrações, procedimento de reinício e validação funcional.
   Não é necessário excluir a branch para reverter uma implantação.

## Limites das evidências

- A cadeia gateway → hook → supervisor é informação operacional útil fornecida
  pelo agente residente. O commit não inclui os arquivos do hook nem um teste de
  reinicialização que permita reproduzir essa conclusão no checkout local.
- A trava por socket abstrato evita supervisores duplicados no mesmo namespace
  de rede; não prova exclusão de bots iniciados manualmente ou em outro namespace.
- O bundle de criação inclui `g-recaptcha-response` com ações `userAdd` e
  `userAddTrial`, corroborando a inspeção anterior. O relatório não inclui resposta
  de criação que demonstre a afirmação universal sobre rejeição pelo backend.
  Não emitir linhas só para testar essa hipótese.
- As explicações sobre ASN, nível máximo de validação, PoW e alteração de canvas
  não vêm acompanhadas de telemetria que estabeleça causalidade. Nos testes
  anteriores desta tarefa, Chrome com sandbox no host e Xvfb iniciou corretamente,
  mas o login permaneceu com desafio pendente. Isso não comprova que o display
  virtual resolva a autenticação.
- Remover literais no commit atual não remove segredos do histórico nem revoga
  credenciais anteriores. A afirmação de ausência de segredos em todo o repositório
  requer uma auditoria de escopo maior que esses sete arquivos.

## Evidências que faltam para homologação

1. Hook e supervisor efetivos, com caminhos, usuário e nomes de variáveis requeridas,
   sem valores secretos; confirmar como o ambiente é carregado.
2. Navegador isolado com CDP somente em loopback, login validado por `/profile`,
   renovação efetiva da sessão e consumo pelo processo do bot. Não agendar um
   daemon como solução enquanto a autenticação continuar inconclusiva.
3. Recuperação demonstrada de processo encerrado e processo travado, com heartbeat
   produzido pelo loop de trabalho, backoff e ausência de consumidores duplicados.
4. Pagamento e pedido persistidos, reconciliação após timeout, linha única por
   pedido pago e retomada da entrega; teste de falha entre cada etapa.
5. Backup restaurável e rollback operacional verificados antes de publicação.

O teste anterior no host não produziu Bearer validado. Não foi gravado
`p2braz_session.json` nem habilitado daemon de renovação. A emissão oficial
autônoma e a homologação ponta a ponta continuam pendentes.
