# BRIEF VISUAL — Nexus PlayTV (para o agente de design)

Documento de handoff. Tudo abaixo é o que o Hermes **não consegue executar com qualidade**
(geração de imagem e refinamento de arte). O resto do site já está no ar em
`https://nexusplay.tv` (frontend Vinext/Next na VPS Njalla, deploy via
`/opt/data/bin/deploy_nexus.sh`).

Repositório: `github.com/meddanielcb/nexus-ecosystem` — branch `coord/agents`
Frontend: `assets/brand_kit_full/NEXUS-Brand-Kit/08-Projeto-Web/`

---

## 1. IMAGENS (prioridade máxima — hoje são fotos de jogos reais, identificáveis)

### Problema
As fotos atuais dos cards de esporte são de partidas reais com clube e patrocinador
identificáveis (faixa de casa de aposta visível, escudo do time, logotipo de emissora
local). Isso derruba a credibilidade da marca e cria risco de uso indevido de imagem.
Não existe banco de imagem gratuito com esporte de elite sem marca identificável —
testado: Unsplash, Pexels e Wikimedia Commons.

### O que gerar (IA, sem texto na imagem)

| Uso | Arquivo | Proporção | Resolução | Formato |
|---|---|---|---|---|
| Card Futebol | `football.webp` | 16:9 | 1920×1080 | WebP q=82 |
| Card Lutas | `ufc.webp` | 16:9 | 1920×1080 | WebP q=82 |
| Card Basquete | `basketball.webp` | 16:9 | 1920×1080 | WebP q=82 |
| Card Velocidade | `motorsport.webp` | 16:9 | 1920×1080 | WebP q=82 |
| Faixa cinema (hoje é retrato e por isso a imagem é cortada) | `cinema-wide.webp` | 21:9 | 2560×1100 | WebP q=82 |
| Hero (topo do site) | `hero-cinema.webp` | 21:9 | 2560×1100 | WebP q=82 |

### Direção de arte (vale para as 6)
- **Paleta**: preto absoluto (#050607) de base, refletores brancos/ciano no topo,
  um reflexo verde-limão (#B7FF3C) na grama/quadra/pista como assinatura da marca.
- **Estádio noturno**, arquibancada cheia desfocada ao fundo, luz de refletor com halo.
- **Nenhum rosto reconhecível, nenhum escudo, nenhuma placa de patrocinador e nenhum
  texto** na imagem. Se aparecer alguém, que seja silhueta ou contraluz.
- Futebol: olhar alto desde a arquibancada, gramado iluminado, bola em movimento.
- Lutas: octógono visto de cima, luz dura no centro, grade em contraluz.
- Basquete: ginásio escuro, aro e tabela em destaque, luz de LED no piso.
- Velocidade: pista molhada à noite, carro em longa exposição, rastro de luz verde.
- Cinema/hero: sala escura com silhuetas de costas assistindo a uma tela luminosa.

### Onde colocar
`08-Projeto-Web/public/media/` (mesmos nomes de arquivo — o código já aponta para eles).

---

## 2. PERSONAGENS / EMBAIXADORES (aguardando decisão + geração)

Ordem de prioridade sugerida e onde cada um entra:

1. **Neymar em "shh"** (já existe, `assets/neymar/neymar_shh_nexus.png`) → hero.
   Ele precisa da versão **paisagem 21:9** — hoje só existe retrato, o que impede o
   uso como faixa de fundo.
2. **Poatan ou Charles Oliveira** → card de Lutas.
3. **Lewis Hamilton com capacete de viseira verde** → card do Teste de 4 Horas.
4. **Vini Jr ou CR7** → bloco de Indicação (30 dias grátis).
5. **Criador de conteúdo "resenha" (Casimiro / IShowSpeed)** → interlude de cinema.

### Regra obrigatória
Usar **sósias gerados por IA**, fisicamente parecidos mas não idênticos, sempre com a
camisa NEXUS PLAYTV. Famoso real sem contrato de imagem derruba campanha em Meta Ads e
Google Ads e cria passivo de direito de imagem. Para tráfego pago, só sósia.

---

## 3. REFINAMENTO DE ARTE (o que eu não tenho olho para fazer)

- **Ranking de latência** no card `02 / VELOCIDADE` (hoje são 3 barras de 2px com logos
  Claro TV+, Sky e YouTube). Funciona e é legível, mas o dono quer que fique no nível do
  resto da arte. Precisa de movimento real: varredura de medição, escala de tempo
  visível e leitura instantânea de "NEXUS 3–5s × concorrência 30–60s".
- **Teste de 4 horas**: o card foi refeito no padrão do `ticket-pass`, mas falta o
  elemento visual de velocidade (capacete com viseira verde, rastro de luz). Precisa da
  imagem do item 1 para virar peça de campanha.
- **Faixa de marcas** (`channel-ribbon`): 14 logos rolando em marquee discreto a 62% de
  opacidade. Revisar peso visual e velocidade — o dono pediu "discreto".
- **Interlude do cinema**: a imagem é retrato (972×1450) e está sendo exibida inteira
  com `object-fit:contain`. Com a versão 21:9 do item 1 volta a ser faixa cheia.

---

## 4. JÁ RESOLVIDO (não repetir)
- Logos de canal: SporTV e Champions League eram azul-marinho (#09043E / #00004B) e
  desapareciam no fundo preto — geradas variantes brancas (`sportv-white.svg`,
  `champions-white.svg`).
- Escudos oficiais dos clubes aplicados na agenda de jogos do PWA (`/app`), usando as
  variantes `-fundo-escuro` do brand kit (`public/media/crests/`).
- Nenhuma menção a "delay" no site: fala-se em latência e tempo de carregamento.
- Emojis removidos das peças de tecnologia.
