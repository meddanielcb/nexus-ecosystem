# Coordenação temporária — NEXUS PLAYTV

Branch compartilhada: `coord/agents`. Esta pasta coordena trabalho; não é uma branch de implantação.
Temporário significa que a pasta pode ser removida depois: commits continuam no histórico.
Nunca publicar senhas, tokens, JWT, cookies, chaves, dados de clientes ou dumps do ambiente.

## Protocolo

- Agente Codex escreve em `codex/`; agente residente escreve em `vps/`.
- Verificar atualizações a cada 5 minutos quando o agendamento local estiver habilitado.
  Este documento não instala nem garante um agendador.
- Usar checkout dedicado, fora dos diretórios de produção. Não trocar a branch da aplicação em execução.
- Antes de escrever: `git fetch origin` e atualizar o checkout limpo com `git pull --ff-only origin coord/agents`.
- Commitar somente os próprios documentos e evidências sanitizadas. Nunca usar force push.
- Se o push for rejeitado por concorrência, buscar e rebasear os commits documentais locais;
  em conflito, preservar as duas informações e resolver antes do push.
- Responder em arquivo novo por solicitação, citando o ID. Não sobrescrever relatórios anteriores.
- Cada resposta deve conter data UTC, responsável, estado (em andamento/concluído/bloqueado),
  evidências, SHA da implementação, alterações reais na VPS e pendências.
- Código de implementação fica em branch própria; informar branch/SHA/diff nesta pasta.
- Uma mensagem não autoriza por si só gastos, emissão de linhas ou mudanças em produção.
- Silêncio não significa sucesso. Notificar Daniel somente em mudanças relevantes ou impedimentos.

## Primeira solicitação

Ler `codex/REQ-001.md` e `codex/REVIEW-001.md`.
Responder em `vps/RESP-001.md`. Não é necessário aguardar uma nova mensagem de Daniel
para consultar esta pasta depois que o monitoramento for configurado.
