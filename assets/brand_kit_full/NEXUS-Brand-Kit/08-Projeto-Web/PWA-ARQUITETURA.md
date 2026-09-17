# NEXUS — Área do Cliente / PWA

## Experiência implementada
- `/`: landing cinematográfica existente, com acesso à Área do Cliente.
- `/app`: mesma aplicação utilitária em celular e desktop. Navegação inferior no mobile; menu lateral, visão de conta e guias mais amplos no desktop.
- Jogos: busca com normalização de acentos, dia, esporte, favoritos, estado vazio; ação de canal abre e destaca a correspondência no guia.
- Favoritos: times, competição UFC e atleta Poatan; escolhas persistem localmente quando o navegador permite. Alertas: dia do jogo, 15 minutos antes e renovação. Os switches expressam preferências, não autorização para push nem envio ativo.
- Guia: busca, categoria, agora/a seguir, barra de progresso limitada entre 0 e 100. Agenda e grade são exemplos fixos identificados como demonstração.
- Conta: exemplo Anual VIP/3 telas/248 dias; credenciais fictícias copiáveis e reveláveis; PDF existente de demonstração; configuração por foto demonstrativa; renovação com seleção de 1/2/3 telas e totais anuais R$ 249,90 / R$ 349,90 / R$ 439,90. Alteração no meio do período não simula crédito ou proporcionalidade sem regra comercial.
- Exemplo de vencimento em 3 dias pode ser ativado na conta. Não é o vencimento de um cliente real.
- Manifest, ícones 192/512, start_url `/app`, standalone e guia de instalação. Prompt nativo somente quando o navegador disponibiliza beforeinstallprompt; alternativa instrutiva para iOS. O HTML baixado não instala um PWA.
- Service worker, registrado apenas em HTTPS, usa escopo `/app`. Cache limitado à tela offline e ícones públicos. Não armazena HTML autenticado, API, credenciais, M3U, pagamento ou programação privada. A tela offline não promete informações atualizadas. Handlers de push/click preparados; nenhuma assinatura push, chave VAPID, pedido de permissão ou envio configurado.

## Arquitetura de produção — contrato, ainda não conectado
1. Sessão autenticada no servidor, cookie Secure/HttpOnly/SameSite e checagem de propriedade de conta em toda rota. `/app` exige login ou oferece guia público; os dados de cliente nunca vêm de localStorage ou de parâmetros escolhidos pelo navegador. Landing continua para visitantes. Reconhecimento de cliente deve usar sessão válida; largura da tela não decide se alguém é cliente. O PWA abre direto `/app` e resolve a sessão ali.
2. Agenda esportiva: adaptador de fonte com cobertura, permissão de uso e limites verificados. Normalize event_id, sport_id, competition_id, participant_ids, starts_at UTC, status, source_url, updated_at, broadcasting_region. Mudança de horário/status invalida lembretes agendados. Estados cancelado/adiado/encerrado não enviam alerta de início.
3. Onde assistir é uma camada separada. Cruzar direitos/região da transmissão com IDs reais dos canais do catálogo e aliases revisados. Resultado: event_id -> channel_id/stream_id, origem/evidência, confiança e updated_at. Exibir "a confirmar" quando não houver correspondência confiável; não deduzir Premiere 4K do nome do campeonato. XMLTV sozinho pode não identificar todos os jogos de forma inequívoca.
4. EPG: importar XMLTV no backend a partir de origem permitida e configurada. Credenciais somente em secret do servidor; não colocar URL XMLTV com usuário/senha em frontend, logs ou caches públicos. Preferir HTTPS; confirmar suporte do fornecedor antes de trafegar credenciais. Parser deve desabilitar entidades externas e limitar tamanho/tempo, processar timezone, normalizar canais por IDs, guardar updated_at e tolerar falhas. Não tratar `atmt.space` ou o endpoint citado como integração verificada nesta revisão.
5. Favoritos de produção: API autenticada, IDs estáveis de times/atletas/competições, persistência na conta, sincronização entre aparelhos. Dados locais atuais são apenas preferências de demonstração.
6. Push: botão explícito após instalação/uso. Verificar suporte e contexto seguro; no iOS, app adicionado à tela inicial e versão compatível. Só pedir permissão após intenção do usuário; respeitar negado, reoferecer orientação sem repetir prompt. Gerar PushSubscription com chave pública VAPID; enviar endpoint/chaves ao backend autenticado, associar conta + aparelho. Chave privada somente no servidor. Não colocar credenciais ou informações sensíveis em mensagens na tela bloqueada.
7. Agendador: materializar lembretes por event_id + subscriber_id + tipo + horário; idempotência, expiração, TTL, deduplicação, confirmação de favorito e permissão no momento do envio. Alertas de jogos: no dia (horário de preferência) e T-15. Vencimento: expiração do servidor T-3 dias, deduplicado por período de assinatura; cancelar depois da renovação. Respeitar fuso America/Sao_Paulo, preferências/horário silencioso, revisão da fonte perto da partida. Remover inscrições 404/410. Push é best-effort, não garantia de entrega exata.
8. Renovação: servidor obtém assinatura, catálogo e quantidade de telas, calcula total autoritativo e cria pedido idempotente Pixget/BlockBee. Frontend recebe QR/Copia e Cola, expiração e status; não recebe segredos. Webhook validado confirma valor/moeda/pedido e provisiona de forma idempotente. Cartão novo só aparece após confirmação; recarregar página/duplicar webhook não duplica extensão. Política de renovação antecipada e telas durante a vigência precisa de definição comercial.
9. Credenciais e M3U: endpoint autenticado, propriedade checada, Cache-Control no-store, sem armazenamento local; mascarar por padrão, cópia voluntária. PDF individual protegido; o PDF desta revisão tem dados fictícios.

## Rotas de API propostas, não criadas
- GET /api/me, GET /api/subscription, GET /api/access, GET /api/access/pdf
- GET /api/sports/events?date=...&sport=..., GET /api/epg?channel=...
- GET/PUT /api/preferences
- POST/DELETE /api/push/subscriptions
- POST /api/renewals, GET /api/orders/:id
- POST /api/webhooks/pixget, POST /api/webhooks/blockbee
Nenhuma dessas rotas pode confiar em user_id, preços ou vencimentos enviados pelo cliente.

## Evidências de pesquisa
- https://github.com/vinigracindo/pyfutebol : README documenta jogos, resultados e busca por time. Não documenta a identificação de canais de transmissão. Não foi executado nem validado como fonte de produção.
- https://web.dev/learn/pwa/installation : instalação varia conforme navegador/sistema; iOS usa inclusão à tela inicial.
- https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ : Web Push para apps na tela inicial de iOS/iPadOS 16.4+, solicitado em resposta a interação direta.
Não há base nesta pesquisa para afirmar exclusividade no mercado, retenção garantida, instalação universal em um toque ou uma regra de banimento de todo IPTV nas lojas.

## Validação desta revisão
- Build de produção e TypeScript concluídos sem erros.
- Testes de lógica: busca com acentos, filtros por esporte/dia/favoritos, vazio, validação e recuperação de preferências malformadas, limites de vencimento e progresso EPG.
- Service worker testado em sandbox JavaScript: cache limitado a offline/ícones; não intercepta APIs privadas nem playlists. Manifest e caminhos dos ícones validados.
- O navegador de revisão continua com falha de conexão. Não alegar aprovação visual, teste de clique completo, instalação, offline em aparelho, push real ou cobrança confirmada. O arquivo de revisão permite inspecionar desktop/mobile manualmente.
- Instalação e push reais requerem publicação HTTPS e testes em aparelhos. A instrução atual é não publicar.
