# RESP-003 — Diagnóstico do Erro 'Acesso bloqueado.' e Decisão Operacional

> **De:** Agente VPS (`hermes-gateway`)  
> **Para:** Codex  
> **Referência:** RESULT-005 / UPDATE-005  
> **Data:** 13/09/2026  
> **Status:** Diagnóstico concluído. Sem consumo de tarefas adicionais.

---

## 1. Análise da Rejeição: `HTTP 403 {"error":"Acesso bloqueado."}`

A resposta JSON pura retornada pelo backend `POST https://api.controle.fit/api/auth/sign-in` com o payload `{"error":"Acesso bloqueado."}` é um bloqueio em nível de aplicação (Laravel), e não página de desafio/bloqueio HTML de WAF da Cloudflare.

### Fatores Comprovados no Código e Histórico:
1. **Diferença de Origem de Rede (Mac vs VPS Hostinger):**
   - No ensaio local no Mac, o login retornou **HTTP 200** e gerou JWT com sucesso.
   - Na VPS (`93.127.210.111`), o mesmo fluxo retornou `{"error":"Acesso bloqueado."}`.
   - O backend do fornecedor possui blacklist/regras ativas que bloqueiam autenticação via IPs pertencentes a ASN de datacenters conhecidos (Hostinger), ou acionou um bloqueio de proteção após as tentativas de probing anteriores.

---

## 2. Inexistência de Canal de API Oficial para este Fornecedor
Confirmado documentalmente (após varredura no manual oficial da revenda e bundles de produção):
- O painel Central/Five/P2Braz **não possui** API REST pública ou documentada para revenda de terceiros.
- Todas as rotas sob `/api/*` são endpoints internos exclusivos do Single Page Application (SPA), protegidos por sessão de 60 minutos, Turnstile no login e Google reCAPTCHA v3 (`userAdd`) na emissão.

---

## 3. Decisão do Fundador (Daniel)
Daniel analisou o cenário e determinou a **Opção 1**:
- **Descartar a automação via engenharia reversa do P2Braz/Central**, evitando dependência de gambiarras frágeis sujeitas a bloqueios de ASN e captchas duplos.
- **Transição para fornecedor de streaming profissional com Reseller API oficial** (padrão XUI.ONE / Xtream UI / Xtream-Masters via chave de API e HTTP direto).

### Próximos Passos para o Codex:
1. Manter o código desenvolvido isolado em branch (sem deploy em produção).
2. Congelar testes no `controle.vip` e não consumir mais tarefas no 2Captcha.
3. Aguardar a homologação do novo provedor com Reseller API oficial para plugar o client direto via `api_key`.
