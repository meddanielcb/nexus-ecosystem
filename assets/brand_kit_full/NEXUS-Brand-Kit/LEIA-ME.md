# NEXUS PlayTV | Kit de marca v1.0
Data: 17/09/2026. Identidade derivada do site aprovado em preto e verde-limão.

## Comece aqui, agente
1. Leia Manual-NEXUS-PlayTV.pdf. Use os SVGs prontos; não redesenhe a marca.
2. Principal em fundo escuro: 01-Logos-SVG/nexus-horizontal-principal.svg (transparente).
3. Fundo claro: nexus-horizontal-preto.svg; se precisar do fundo incluso, nexus-horizontal-fundo-claro.svg.
4. Avatar/PWA: nexus-simbolo-fundo-escuro.svg ou nexus-icon-512.png. Favicon: favicon.svg + favicon.ico.
5. Importe 05-Tokens/fonts.css e nexus.css, ajustando apenas os caminhos à estrutura do projeto.
6. Para atualizações futuras, preserve símbolo, proporções e tipografia dos arquivos. Não substitua por letra N digitada.

## Conteúdo
01-Logos-SVG: horizontal, vertical e símbolo; 7 combinações cada. Letras em curvas, sem dependência de fonte externa.
02-Logos-PNG: versões transparentes e com fundo. Horizontal 320/640/1280/2560 px de largura; vertical/símbolo 256/512/1024 px.
03-Icones-Favicon: SVG, ICO multirresolução, PNG 16/32/48/64/128/180/192/256/512/1024; apple-touch-icon e exemplo de manifest.
04-Fontes: Space Grotesk 400/500/600/700; Barlow Condensed 600/700/800, originais TTF e licenças SIL OFL 1.1.
05-Tokens: JSON e CSS de cores, fontes e hierarquia.
06-Handoff: instruções, inventário e checksums.

## Convenções de nomes
principal: símbolo verde + letras claras, transparente, para fundo escuro.
branco: monocromático claro, transparente, para fundo escuro.
preto: monocromático preto, transparente, para fundo claro.
verde: monocromático verde, transparente, somente sobre fundo escuro.
fundo-escuro / fundo-claro / fundo-verde: fundo opaco incluído.

## Construção e tamanhos
Não esticar nem cortar os SVGs. A caixa contém margem interna; adicione área livre externa conforme o manual.
Horizontal: mínimo recomendado 160 px de largura; 180-220 px em cabeçalho desktop. Mobile: 140-160 px somente se PLAYTV permanecer legível; caso contrário use símbolo.
Vertical: mínimo 120 px de largura. Símbolo: mínimo 24 px de caixa no produto; favicon usa os arquivos próprios de 16/32 px.
Use PNG em 2x ou 3x a dimensão de exibição. SVG é preferível no produto.
A exportação horizontal padroniza o lettering em Space Grotesk. Arquivos legados do site tinham Arial em alguns SVGs, embora o layout atual já use Space Grotesk. Este kit é a referência consolidada; a troca no repositório é uma tarefa posterior, não foi feita por este pacote.

## Aplicação e texto
Landing: entretenimento primeiro; esporte, filmes e séries; imagens cinematográficas reais com disponibilidade de catálogo confirmada. App: utilidade, leitura e navegação; evitar reaplicar o hero de vendas na conta.
Escrever NEXUS PlayTV em texto. Usar caixa alta NEXUS / PLAYTV no logotipo. Manter nomes: StreamCore™ Ultra-P2P; Engine Go™ Anti-Delay; Nexus Vision AI™; Protocolo de Entrega Atômica 24/7. Não adicionar ® nem sugerir registro concluído.
Não criar promessas, depoimentos, contagens, urgência, garantias, preços ou parcerias como parte do design.

## Movimento
Botões: 140 ms. Abas/modal: 220 ms. Galeria: 18 s por posição, pausa e controle manual. Parallax: até 32 px, apenas no fundo. Digitação: um título, largura reservada, sem layout shift. Honrar prefers-reduced-motion; não usar brilho pulsante em texto de leitura.

## Integração dos ícones
Copie os arquivos para /brand ou ajuste os caminhos no manifest de exemplo. Ele é referência, não substitui configuração/auth/rotas do app.
<head>
<link rel="icon" href="/brand/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/brand/favicon.ico">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon.png">
<meta name="theme-color" content="#080B09">
</head>
O PNG 512 tem fundo sólido e símbolo dentro da área central segura; adequado à entrada maskable. Sem cantos transparentes pré-recortados nos ícones PWA.

## Fontes e impressão
Preserve as licenças incluídas. Não renomear as famílias internamente. Os arquivos não foram modificados; nomes de arquivo apenas descritivos.
A referência de cor é sRGB/HEX. CMYK do manual é conversão matemática aproximada, não uma prova de impressão. Verde-limão em tela não tem reprodução garantida em CMYK; fechar com gráfica e prova física.
Sem atribuição de Pantone por aproximação.

## Proveniência
Símbolo geométrico original já existente no projeto NEXUS. Lettering consolidado com a família usada no site. Fontes originais do pacote atual do site; licenças: https://github.com/google/fonts/tree/main/ofl/spacegrotesk e https://github.com/google/fonts/tree/main/ofl/barlowcondensed.
O kit inclui marcas de terceiros em uma biblioteca separada, sem tratá-las como propriedade NEXUS.
Nenhuma alteração ou publicação do site foi realizada nesta entrega.

## Ampliação de ativos de conteúdo
94 clubes de futebol: 40 brasileiros (catálogos das Séries A e B) e 54 europeus em nove países. Mais Lakers e Warriors. O índice nominal fica em 07-Marcas-e-Escudos/INDICE-TIMES.md.
Competições em assets/leagues: Champions League, Brasileirão, Libertadores, Premier League, NBA, Formula 1 e UFC, com arquivos de origem e registro de fontes.
assets/branding, assets/crests, assets/leagues, assets/platforms e assets/banners são diretórios prontos para integração. O espelho em assets repete os mestres para facilitar a cópia; não é uma versão diferente.
As artes de filmes/séries são as da revisão, sem alegação de lançamento atual ou tendência.
Decisão de cor: preservar preto #050607 / app #080B09 e verde #B7FF3C aprovados. Os tons ciano #00F2FE/#4FACFE citados no comentário externo não substituem essa decisão.


## Entrega ampliada: código incluído
Leia `COMECE-AQUI-AGENTE.md`. O projeto completo está em `08-Projeto-Web/` e as prévias em `09-Previas/`.
