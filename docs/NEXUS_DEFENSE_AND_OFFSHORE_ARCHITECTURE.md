# 🛡️ Nexus PlayTV — Estratégia de Defesa, Blindagem e Arquitetura Offshore

> **Classificação:** Documento Estratégico & Arquitetura de Continuidade  
> **Objetivo:** Proteger a operação do Nexus PlayTV contra ataques de concorrentes (DDoS, denúncias de domínio, abuso de hosting, tentativas de derrubada jurídica e bloqueio financeiro).

---

## 🎯 1. O Cenário de Ameaças do Mercado
O mercado de streaming e IPTV no Brasil movimenta cifras milionárias e é altamente competitivo. Concorrentes estabelecidos utilizam táticas desleais para tentar eliminar novos players:
1. **DDoS Massivo:** Ataques de negação de serviço com envio de 50 Gbps a 100 Gbps de tráfego UDP/SYN para tirar o IP do ar.
2. **Denúncias Abusivas de Domínio:** Abertura de disputas no registrar do domínio para suspensão arbitrária do DNS.
3. **Denúncias no Provedor de VPS:** Notificações extrajudiciais em provedores com sede no Brasil (ex: Hostinger Brasil) forçando o desligamento da VPS.
4. **Ataques de Engenharia Social & Denúncia de Chaves PIX:** Tentativa de denunciar chaves de recebimento em bancos para travar fundos.

---

## 🏗️ 2. A Blindagem em 5 Camadas (Arquitetura Inderrubável)

### Camada 1: Domínio Blindado & Anônimo (Offshore Registrar)
- **Regra de Ouro:** NUNCA registrar domínios `.com.br` (o Registro.br expõe CPF/CNPJ, endereço físico e telefone abertamente no WHOIS público).
- **Extensões Recomendadas:** `.tv`, `.io`, `.net` ou `.live`.
- **Registrars Offshore Recomendados:**
  - **Njalla (Ilhas Virgens Britânicas / Finlândia):** Atua como "Privacy Shield" legal. O domínio é registrado legalmente pela própria Njalla, que atua como proxy jurídico. Não respondem a terceiros nem a concorrentes. Pagamento anônimo via Cripto (BTC/XMR/USDT).
  - **Porkbun / Namecheap:** Alternativas sólidas com WHOIS Privacy Shield ativo por padrão.
- **Estratégia de Redundância (Mirror Domains):** Manter 1 domínio principal e 2 domínios espelhos de reserva configurados no mesmo Caddy/Nginx. Se um registrar sofrer ataque, o CNAME migra para o reserva em minutos.

### Camada 2: Ocultação Total do IP Real da VPS (Proxy Reverso & Anti-DDoS)
- **Problema:** Se o DNS apontar diretamente para o IP da VPS (`93.127.210.111`), qualquer ataque DDoS derruba o servidor.
- **Solução:** O tráfego Web (Landing Page e Webhooks) deve sempre passar por uma camada de Proxy com proteção Anti-DDoS:
  - O DNS aponta apenas para os IPs do Proxy.
  - O IP real da VPS da aplicação permanece **100% SECRETO**.
  - O Proxy absorve ataques de dezenas de gigabits por segundo, filtra requisições maliciosas e entrega apenas tráfego legítimo para a VPS.
  - **Firewall de Borda (VPS):** A VPS só aceita conexões HTTP/HTTPS originadas dos blocos de IP oficiais do Proxy; qualquer acesso direto ao IP da máquina na porta 80/443 é sumariamente descartado (`DROP`).

### Camada 3: Hospedagem Offshore DMCA-Ignored (Infraestrutura Definitiva)
- **Status Atual:** A Hostinger atende perfeitamente à fase de validação, testes e início das vendas.
- **Migração para Escala:** Para suportar volumes elevados e blindar contra notificações no Brasil, a infraestrutura será espelhada em provedores internacionais **DMCA-Ignored**:
  - **Alexhost (República da Moldávia):** Datacenter subterrâneo próprio, imune a ordens estrangeiras e denúncias arbitrárias de concorrentes. Aceita pagamentos em criptomoedas.
  - **FlokiNET (Islândia / Romênia):** Provedor focado em liberdade de expressão e privacidade extrema.
  - **Novogara / HostKey (Holanda):** Conectividade ultra-rápida para a América Latina com tolerância a notificações.
- **Custo:** Praticamente o mesmo valor de uma VPS convencional ($7 a $12 USD/mês).

### Camada 4: Resiliência Financeira & Gateway de Pagamentos
- **Separação Institucional:** Nunca utilizar contas bancárias de pessoas físicas ou chaves PIX de bancos de varejo convencionais (Itaú, Nubank, Bradesco).
- **Intermediação PixGet:** O checkout PIX opera com validação de CPF na Receita Federal e assinatura criptográfica HMAC-SHA256, blindando a origem do sistema.
- **Cripto Direta (BlockBee / Carteira Própria):** O bot mantém pagamentos em USDT e Bitcoin ativos diretamente na blockchain. Criptomoeda não sofre chargeback, não pode ser congelada por denúncia de concorrente e fornece rota financeira soberana.

### Camada 5: Resiliência nos Canais de Venda (Telegram & WhatsApp)
- **Telegram (`@Nexus_playtvbot`):** Infraestrutura nativa na VPS. O Telegram é uma das plataformas mais resistentes a censura do mundo e não derruba robôs de automação por picuinhas de terceiros. Mesmo que qualquer site caia, o robô no Telegram continua 100% ativo vendendo e ativando acessos.
- **WhatsApp (Evolution API):** Quando for ativado na VPS, utilizará números virtuais dedicados (chips virtuais descartáveis), sem qualquer vínculo com números pessoais.

---

## 📋 3. Plano de Execução & Checklist de Implementação

- [x] **Fase 1 (Atual - Concluída):** Sistema 100% testado, estável e operacional na VPS Hostinger com bot Telegram, PixGet, MasterX API e IBO Player.
- [ ] **Fase 2 (Aquisição do Domínio Blindado):**
  - Registro de domínio internacional (`.tv` ou `.io`) no Njalla ou Porkbun com Whois Privacy 100% anônimo.
  - Apontamento de DNS com proteção de proxy.
- [ ] **Fase 3 (Subida da Landing Page Web):**
  - Deploy da Single Page Dark Mode (`#0a0b0e` + `#00f2fe`) com checkout PixGet nativo e entrega atômica.
- [ ] **Fase 4 (Espelhamento Offshore):**
  - Criação de imagem Docker do ecossistema e contratação de VPS na Moldávia (Alexhost) ou Holanda.
  - Deploy em paralelo com backup automático diário sincronizado.
