# NEXUS — entrega completa para o agente

Este ZIP reúne o kit visual e o código-fonte da última revisão disponível. Não significa que as integrações de produção estejam concluídas. Não publicar sem autorização do Daniel.

## Onde está cada parte
- `01-Logos-SVG` a `07-Marcas-e-Escudos`: identidade, fontes, tokens e imagens, conforme o manual.
- `assets/`: cópias organizadas de branding, brasões, ligas, plataformas e banners para integração.
- `08-Projeto-Web/`: projeto completo exportado do repositório, incluindo fontes, assets locais, dependências declaradas, lockfile e configurações.
- `09-Previas/`: HTMLs autônomos para inspecionar as interfaces sem instalar dependências. A prévia App inclui landing e área do cliente; a revisão v2 registra a landing. Não executam pagamentos nem instalam o PWA.
- `06-Handoff/PARA-O-AGENTE.md`: direção de arte e uso dos ativos.

## Executar o código
Requisitos: Node.js >=22.13 e pnpm 11.25.0, conforme package.json.

```sh
cd 08-Projeto-Web
pnpm install --frozen-lockfile
pnpm dev
```

Abra o endereço local exibido no terminal. Rotas: `/` para landing e `/app` para PWA/área do cliente. Em um checkout limpo, o script escolhe automaticamente o perfil portable. O projeto usa React, TypeScript, Tailwind e Vinext/Vite, com estrutura de rotas compatível com Next. Não é uma pasta de HTML estático. Para build local: `pnpm build`; para prévia do Worker gerado: `pnpm start`. A instalação em uma máquina externa não foi executada nesta entrega.

## Mapa de implementação
| Recurso | Arquivos em 08-Projeto-Web |
|---|---|
| Landing, galeria e movimento | app/page.tsx, app/globals.css, app/media.ts |
| Planos e checkout | app/commerce.tsx, app/content.ts |
| Ativação por foto | app/activation.tsx |
| Área do cliente, jogos, favoritos, renovação | app/app/page.tsx, app/app/model.ts, app/client.css |
| Manifesto e service worker | public/manifest.webmanifest, public/nexus-sw.js |
| Ícones e offline | public/app-assets/ |
| Arquitetura e integrações pendentes | PWA-ARQUITETURA.md |
| Revisão e fontes dos assets | REVISAO.md, ASSET-SOURCES.json |

## Estado real
Implementados: interfaces responsivas, navegação, seleção de telas/preços, modal demonstrativo de checkout, galeria, parallax, título animado, pausa/reduced-motion, favoritos locais, busca e filtros do guia demonstrativo, conta ilustrativa, manifesto, service worker e fallback offline.

Pendentes: autenticação de clientes, backend de assinatura/credenciais, Pixget e BlockBee, webhooks e provisionamento idempotente, cupons reais, ativação Vision AI, agenda esportiva/EPG reais, favoritos sincronizados, VAPID e envio de push, WhatsApp/Telegram e PDF individual. StreamCore e Engine Go são apresentados comercialmente: os motores de transmissão não estão implementados neste frontend.

A lógica de preços, filtros, preferências e restrições de cache foi testada na revisão anterior; build e TypeScript passaram. O navegador de revisão estava indisponível: não declarar teste visual completo, teclado/toque de todos os controles, instalação em dispositivo, push, cobrança ou integração ponta a ponta. Nesta entrega verificou-se integridade do ZIP e igualdade de todos os arquivos exportados com o repositório, sem mudanças no código.

## Aplicação no repositório do agente
Copie o conteúdo de `08-Projeto-Web` para uma branch de integração e revise conflitos antes de substituir arquivos existentes. Não sobreponha um backend já implementado. Preserve os contratos e conecte as interfaces aos serviços reais. `db/schema.ts` e exemplos do starter não são um banco de assinaturas pronto.

O kit visual é posterior à revisão do site: seus logos com letras convertidas em curvas são a referência para a identidade; o código exportado conserva os assets usados na última revisão, sem substituição silenciosa. Consulte o handoff ao aplicar os novos masters. Preserve preto/verde-limão, preços aprovados e tecnologias nomeadas. Não invente prova social, catálogo, direitos de transmissão ou resultados de desempenho.

Não foram empacotados node_modules, builds, caches, histórico Git ou credenciais. Dependências são reconstruídas pelo lockfile. Esta entrega não publica o site.

Commit de origem: `e2e87a2f59f57b5de322e21a7397d48b9e56026e`.
