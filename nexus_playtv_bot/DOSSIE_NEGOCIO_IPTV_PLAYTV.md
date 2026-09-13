# 📡 Dossiê Executivo & Modelo de Negócio: Nexus PlayTV

## 1. O Mercado & Matemática Financeira (Alta Margem & Recorrência)
- **Custo Unitário (Crédito Atacado P2P / Xtream API):** R$ 4,40 a R$ 8,00 por tela/mês (média R$ 6,00).
- **Planos Comerciais de Venda:**
  - **Mensal (1 Tela):** R$ 34,90 (Lucro Líquido: ~R$ 28,90 / margem de 480%)
  - **Trimestral (1 Tela):** R$ 89,90 (Custo 3 créditos = R$ 18,00 | Lucro Líquido: R$ 71,90)
  - **Semestral:** R$ 149,90 (Custo 6 créditos = R$ 36,00 | Lucro Líquido: R$ 113,90)
  - **Anual Família (2 Telas):** R$ 249,90 (Custo 24 créditos = R$ 105,00 | Lucro Líquido: R$ 144,90)
- **Recorrência & LTV:** 100 clientes ativos = R$ 2.890,00 de lucro líquido recorrente mensal; 500 clientes = R$ 14.450,00/mês.

---

## 2. A Máquina de Vendas & Gatilhos Mentais
O funil padrão de maior conversão do mercado opera em 4 etapas:
1. **Gatilho da Degustação Imediata (Teste Grátis 2h a 4h):**
   - O cliente não compra no escuro. O bot gera um teste automático de 4 horas sem pedir cartão ou CPF.
   - O teste expira e o bot envia mensagem com oferta especial para assinar com desconto nos próximos 30 minutos.
2. **Gatilho da Economia Comparada:**
   - "Premiere (R$ 59,90) + Netflix 4K (R$ 55,90) + Disney+ (R$ 43,90) + HBO (R$ 34,90) = R$ 194,60/mês."
   - "Nexus PlayTV: Todos os canais + 120.000 filmes e séries por apenas R$ 34,90/mês."
3. **Gatilho da Estabilidade Anti-Travamento (P2P / CDN Híbrida):**
   - A maior objeção de quem compra IPTV é: *"trava na hora do jogo do Flamengo/Corinthians"*.
   - A narrativa comercial enfatiza: Servidores P2P com tecnologia anti-bloqueio de operadoras e tráfego distribuído.

---

## 3. Fluxo de Entrega Automática (100% Sob Demanda)
Assim que o Pixget (DePix) ou Cripto (BlockBee/CryptoBot) confirma o pagamento:
1. O backend chama o endpoint do painel de revenda via API REST (`/api/user/create` ou `/player_api.php`).
2. O painel gera login, senha e consome 1 crédito.
3. O bot entrega imediatamente ao cliente:
   - 👤 Usuário: `nexus_1092`
   - 🔑 Senha: `play_99812`
   - 🌐 Servidor / URL DNS: `http://servidor-cdn.me:80`
   - 🔗 Link M3U completo para apps compatíveis.
   - 📲 Botões interativos com o manual do seu app (Smarters Pro, TiviMate, XCIPTV, IBO Player).

---

## 4. Agente de Atendimento & Suporte IA (Nível 1)
O bot terá um menu de autoatendimento e assistente inteligente para as principais dúvidas:
- Como instalar na TV Samsung (Tizen)
- Como instalar na TV LG (webOS)
- Como instalar no TV Box / Firestick (Android)
- Como trocar o DNS quando a operadora faz Traffic Shaping
- Como renovar assinatura antes do vencimento
