# ESPECIFICAÇÃO TÉCNICA E DIRETRIZES DE ASSETS VISUAIS — NEXUS PLAYTV
**Versão:** 2.0 — Produção Oficial Fotográfica e Cinematográfica Real  
**Destino:** WebPlayer Nexus (`play.nexusplay.tv`) & Nexus Stick / TV Box  
**Entrega:** Arquivo único compactado (`NEXUS-Assets-Oficiais.zip`) contendo estrutura de pastas e `manifest.json`.

---

## 1. REGRAS GERAIS E CRITÉRIOS DE QUALIDADE INEGOCIÁVEIS

1. **PROIBIDO USO DE ILUSTRAÇÃO OU ARTE SINTÉTICA DE IA:**
   * Nenhuma imagem com textura plástica, rostos deformados, iluminação irreal ou aspecto de inteligência artificial.
   * O cliente Nexus exige o padrão **RedPlay TV, BTV 13, Claro tv+ e Apple TV+**.
   * Todos os assets devem ser **stills cinematográficos originais em 4K/Full HD**, fotos esportivas oficiais de agências (Getty Images, Reuters, AP, UEFA, NBA, UFC) ou capturas diretas de transmissões esportivas e filmes de Hollywood.
2. **PESSOAS REAIS, ESTRELAS MUNDIAIS E MARCAS OFICIAIS:**
   * A plataforma opera com infraestrutura offshore anônima, blindada e sem KYC. Usaremos **os maiores ícones do planeta**: Messi, Cristiano Ronaldo, Vini Jr, Haaland, LeBron James, Steph Curry, Alex Poatan, Timothée Chalamet, Cillian Murphy, Tom Cruise, Keanu Reeves, Batman, etc.
3. **TRATAMENTO DE COR E COMPOSIÇÃO (DEGRADÊ INFERIOR OBRIGATÓRIO):**
   * **Base e Rodapé Escurecidos:** Os 35% inferiores de toda imagem e vídeo DEVEM ter um fade/vinheta suave para preto profundo (`#0b0e0f`), garantindo que a tipografia, botões e cards que ficam na frente nunca disputem leitura com o corpo ou cenário.
   * **Sem Textos ou Logos Embutidos:** Não escreva títulos, anos, notas ou nomes nos cards nem nos banners. Todos os textos são renderizados em tempo real pelo código do WebPlayer.
4. **PADRÃO DE FORMATOS E COMPACTAÇÃO:**
   * **Imagens:** Formato **WebP**, compressão lossy de alta qualidade (qualidade 88-92%), peso entre **90 KB e 180 KB** por imagem (para carregamento instantâneo em conexões móveis e TV Box).
   * **Vídeos (Cinemagraphs):** Formato **MP4 (H.264 / AAC)**, 30 FPS, sem áudio (muted), com **loop infinito contínuo e invisível** (seamless loop), bitrate calibrado entre 1.5 e 2.5 Mbps, duração ideal de **4 a 8 segundos**.

---

## 2. ESTRUTURA DE DIRETÓRIOS EXIGIDA NO ARQUIVO ZIP

```text
NEXUS-Assets-Oficiais.zip
├── manifest.json
├── banners/
│   ├── 01-futebol.webp
│   ├── 01-futebol-1080p.mp4
│   ├── 01-futebol-720p.mp4
│   ├── 02-basquete.webp
│   ├── 02-basquete-1080p.mp4
│   ├── 02-basquete-720p.mp4
│   ├── 03-cinema.webp
│   ├── 03-cinema-1080p.mp4
│   ├── 03-cinema-720p.mp4
│   ├── 04-series.webp
│   ├── 04-series-1080p.mp4
│   ├── 04-series-720p.mp4
│   ├── 05-combate.webp
│   ├── 05-combate-1080p.mp4
│   └── 05-combate-720p.mp4
└── cards/
    ├── filmes/
    │   ├── 01-lancamentos.webp
    │   ├── 02-top50.webp
    │   ├── 03-cinema.webp
    │   ├── 04-acao.webp
    │   ├── 05-comedia.webp
    │   ├── 06-drama.webp
    │   ├── 07-terror.webp
    │   ├── 08-suspense.webp
    │   ├── 09-ficcao.webp
    │   ├── 10-animacao.webp
    │   ├── 11-nacionais.webp
    │   ├── 12-documentarios.webp
    │   ├── 13-crime.webp
    │   ├── 14-guerra.webp
    │   ├── 15-animes.webp
    │   ├── 16-faroeste.webp
    │   ├── 17-romance.webp
    │   ├── 18-religiosos.webp
    │   ├── 19-aventura.webp
    │   ├── 20-marvel.webp
    │   ├── 21-dc.webp
    │   ├── 22-standup.webp
    │   ├── 23-uhd4k.webp
    │   ├── 24-thriller.webp
    │   ├── 25-natal.webp
    │   ├── 26-shows-festivais.webp
    │   ├── 27-legendados.webp
    │   └── 28-adultos-18.webp
    └── series/
        ├── 01-doramas.webp
        ├── 02-novelas.webp
        ├── 03-crunchyroll.webp
        ├── 04-brasil-paralelo.webp
        ├── 05-desenhos.webp
        ├── 06-series-tv.webp
        └── 07-series-adultos-18.webp
```

---

## 3. ESPECIFICAÇÃO DETALHADA DOS BANNERS HERO (FUNDO ROTATIVO DA HOME)

* **Dimensões das Imagens:** `1920x1080` pixels (Aspect Ratio 16:9), WebP.
* **Dimensões dos Vídeos 1080p:** `1920x1080`, 30 fps, H.264, loop contínuo.
* **Dimensões dos Vídeos 720p:** `1280x720`, 30 fps, H.264, loop contínuo (modo performance para Stick).
* **Movimento do Vídeo:** Movimento sutil e contínuo (fumaça, poeira de refletores, chuva fina, feixes de luz cruzando a quadra, respiração do atleta, bandeiras da torcida balançando). Não usar cortes bruscos de câmera.

### Banner 01: TV ao Vivo — Futebol Champions League / Libertadores
* **Imagem:** `banners/01-futebol.webp` | **Vídeos:** `01-futebol-1080p.mp4`, `01-futebol-720p.mp4`
* **Assunto Real:** Vini Jr ou Haaland em close de alta velocidade comemorando gol sob chuva fina e iluminação dramática de refletores de um estádio de 80 mil pessoas lotado ao fundo.
* **Movimento do Vídeo:** Gotas de chuva cortando a luz dos holofotes, vapor de ar saindo do atleta, bandeiras da torcida ao fundo em movimento suave.

### Banner 02: Jogos do Dia — NBA / Basquete Mundial
* **Imagem:** `banners/02-basquete.webp` | **Vídeos:** `02-basquete-1080p.mp4`, `02-basquete-720p.mp4`
* **Assunto Real:** LeBron James enterrando com força na cesta pelos Lakers ou Stephen Curry no ápice do arremesso pelos Warriors, com a quadra de madeira brilhante e feixes de luz da arena.
* **Movimento do Vídeo:** Feixes de luz dos holofotes da arena varrendo o topo, rede da cesta oscilando suavemente, flashes de fotógrafos ao fundo.

### Banner 03: Cine Nexus — Superprodução de Cinema
* **Imagem:** `banners/03-cinema.webp` | **Vídeos:** `03-cinema-1080p.mp4`, `03-cinema-720p.mp4`
* **Assunto Real:** Cena cinematográfica real de *Duna 2* (Timothée Chalamet com os olhos azuis de especiaria no deserto escuro de Arrakis) ou Cillian Murphy com chapéu e olhar penetrante em *Oppenheimer*.
* **Movimento do Vídeo:** Partículas de areia/poeira cósmica flutuando no ar, luz anamórfica quente passando suavemente pela lente da câmera.

### Banner 04: Séries Nexus — Drama / Crime Noir
* **Imagem:** `banners/04-series.webp` | **Vídeos:** `04-series-1080p.mp4`, `04-series-720p.mp4`
* **Assunto Real:** Cillian Murphy como Thomas Shelby em *Peaky Blinders* de sobretudo e boina caminhando em uma rua de paralelepípedos molhada à noite, ou Pedro Pascal em *The Last of Us*.
* **Movimento do Vídeo:** Fumaça/vapor subindo suavemente de bueiros e chaminés, névoa volumétrica passando ao redor da silhueta, reflexos de luz tremulando na água do asfalto.

### Banner 05: Combate ao Vivo — UFC / Octógono Mundial
* **Imagem:** `banners/05-combate.webp` | **Vídeos:** `05-combate-1080p.mp4`, `05-combate-720p.mp4`
* **Assunto Real:** Alex Poatan (Pereira) encarando no centro do octógono do UFC com os punhos enfaixados, expressão implacável e o cinturão mundial, iluminação zenital fria focada nele.
* **Movimento do Vídeo:** Névoa de gelo seco rastejando no tablado do octógono, feixes de luz azuis e dourados cruzando no teto da arena.

---

## 4. CARDS DE GÊNEROS — FILMES (1920x1080 WebP, 16:9, ~100 KB)

Cada card de gênero deve usar um still ou captura fotográfica oficial em altíssima definição de um filme consagrado e reconhecível pelo grande público:

1. **`cards/filmes/01-lancamentos.webp` — Lançamentos 2026**
   * *Referência Real:* Close cinematográfico de um blockbuster recente de cinema (ex: Gladiador 2 com Paul Mescal na arena coliseu ao pôr do sol sombrio).
2. **`cards/filmes/02-top50.webp` — Top 50 Mais Assistidos**
   * *Referência Real:* Cena épica de *Vingadores: Ultimato* com os heróis reunidos no campo de batalha destruído.
3. **`cards/filmes/03-cinema.webp` — Sucessos do Cinema**
   * *Referência Real:* Tom Cruise acelerando de moto na borda do precipício em *Top Gun: Maverick* ou *Missão: Impossível*.
4. **`cards/filmes/04-acao.webp` — Ação & Adrenalina**
   * *Referência Real:* Keanu Reeves em pose de tiro tático empunhando pistola com terno sob chuva e néon em *John Wick 4*.
5. **`cards/filmes/05-comedia.webp` — Comédia**
   * *Referência Real:* Ryan Reynolds em pose cômica e sarcástica com a máscara de *Deadpool*.
6. **`cards/filmes/06-drama.webp` — Drama & Emoção**
   * *Referência Real:* Leonardo DiCaprio em cena dramática no topo da proa em *Titanic* ou em *O Regresso*.
7. **`cards/filmes/07-terror.webp` — Terror & Horror**
   * *Referência Real:* A freira demoníaca de *Invocação do Mal* ou a máscara icônica de Ghostface em *Pânico* na penumbra.
8. **`cards/filmes/08-suspense.webp` — Suspense & Mistério**
   * *Referência Real:* Edward Norton e Brad Pitt em *Clube da Luta* ou Christian Bale sob chuva pesada em suspense psicológico.
9. **`cards/filmes/09-ficcao.webp` — Ficção Científica & Fantasia**
   * *Referência Real:* Ryan Gosling encarando o holograma gigante rosa em *Blade Runner 2049* ou Matthew McConaughey no traje espacial em *Interestelar*.
10. **`cards/filmes/10-animacao.webp` — Animação & Família**
    * *Referência Real:* Miles Morales saltando de cabeça para baixo entre os arranha-céus iluminados em *Homem-Aranha no Aranhaverso*.
11. **`cards/filmes/11-nacionais.webp` — Cinema Nacional**
    * *Referência Real:* Wagner Moura com o uniforme do BOPE e boina preta como Capitão Nascimento em *Tropa de Elite*.
12. **`cards/filmes/12-documentarios.webp` — Documentários**
    * *Referência Real:* Planeta Terra visto do espaço com iluminação solar na curva atmosférica ou leão majestoso em close no documentário da BBC.
13. **`cards/filmes/13-crime.webp` — Crime & Máfia**
    * *Referência Real:* Al Pacino sentado em sua poltrona com fumaça de charuto em *O Poderoso Chefão*.
14. **`cards/filmes/14-guerra.webp` — Guerra & História**
    * *Referência Real:* Soldados desembarcando na praia da Normandia com fumaça e explosões em *O Resgate do Soldado Ryan*.
15. **`cards/filmes/15-animes.webp` — Animes & Longas**
    * *Referência Real:* Still cinematográfico oficial de *Demon Slayer: Mugen Train* (Rengoku com espada de chamas) ou *Attack on Titan*.
16. **`cards/filmes/16-faroeste.webp` — Faroeste & Western**
    * *Referência Real:* Clint Eastwood de poncho e chapéu com charuto no canto da boca em *Três Homens em Conflito*.
17. **`cards/filmes/17-romance.webp` — Romance**
    * *Referência Real:* Ryan Gosling e Rachel McAdams se abraçando sob chuva torrencial em *Diário de uma Paixão*.
18. **`cards/filmes/18-religiosos.webp` — Religiosos & Fé**
    * *Referência Real:* Still cinematográfico de *A Paixão de Cristo* (Jim Caviezel) ou Charlton Heston abrindo o Mar Vermelho em *Os Dez Mandamentos*.
19. **`cards/filmes/19-aventura.webp` — Aventura & Exploração**
    * *Referência Real:* Harrison Ford com chicote, tocha e chapéu em caverna antiga em *Indiana Jones*.
20. **`cards/filmes/20-marvel.webp` — Marvel Studios**
    * *Referência Real:* Robert Downey Jr. com a armadura iluminada do Homem de Ferro preparando propulsor de mão.
21. **`cards/filmes/21-dc.webp` — DC Universe**
    * *Referência Real:* Robert Pattinson como Batman saindo das sombras com a bat-armadura molhada pela chuva de Gotham.
22. **`cards/filmes/22-standup.webp` — Stand-up Comedy**
    * *Referência Real:* Dave Chappelle ou Chris Rock no centro de um palco de teatro escuro iluminado por holofote zenital.
23. **`cards/filmes/23-uhd4k.webp` — Resolução Máxima UHD 4K**
    * *Referência Real:* Close ultra macro no olho de um ator de cinema com reflexo do set e nitidez absurda de poros e cores.
24. **`cards/filmes/24-thriller.webp` — Thriller Psicológico**
    * *Referência Real:* Anthony Hopkins como Hannibal Lecter encarando através do vidro da cela em *O Silêncio dos Inocentes*.
25. **`cards/filmes/25-natal.webp` — Especial de Natal**
    * *Referência Real:* Macaulay Culkin gritando com as mãos no rosto com as luzes de Natal ao fundo em *Esqueceram de Mim*.
26. **`cards/filmes/26-shows-festivais.webp` — Shows & Festivais Musicais**
    * *Referência Real:* Travis Scott, Coldplay ou Alok no palco principal do Rock in Rio / Lollapalooza com labaredas de fogo e 100 mil pessoas com pulseiras de LED acesas.
27. **`cards/filmes/27-legendados.webp` — Filmes Legendados**
    * *Referência Real:* Enquadramento clássico de cinema europeu com iluminação dramática de arte (ex: *Parasita* de Bong Joon-ho).
28. **`cards/filmes/28-adultos-18.webp` — Conteúdo Adulto (+18 Restrito)**
    * *Referência Real:* Silhueta noturna estética e sofisticada em contraluz com sombras vermelhas e néon escuro (estilo thriller erótico noir, sem nudez explícita no card para preservar a elegância do app).

---

## 5. CARDS DE GÊNEROS — SÉRIES (1920x1080 WebP, 16:9, ~100 KB)

1. **`cards/series/01-doramas.webp` — Doramas / K-Drama**
   * *Referência Real:* Still oficial da cena de chuva com guarda-chuva amarelo de *Pousando no Amor* (*Crash Landing on You*) ou cena de tensão de *Round 6* (*Squid Game*).
2. **`cards/series/02-novelas.webp` — Novelas & Teledramaturgia**
   * *Referência Real:* Cena épica noturna de novela consagrada (ex: Carminha em *Avenida Brasil* ou cena luxuosa de *Pantanal*).
3. **`cards/series/03-crunchyroll.webp` — Crunchyroll / Animes Exclusivos**
   * *Referência Real:* Still oficial de *Jujutsu Kaisen* (Satoru Gojo retirando a venda com os olhos azuis faiscando energia).
4. **`cards/series/04-brasil-paralelo.webp` — Brasil Paralelo & Documentários Históricos**
   * *Referência Real:* Palácio histórico de Petrópolis ou estátua histórica iluminada por luz noturna com arquivo histórico.
5. **`cards/series/05-desenhos.webp` — Desenhos Clássicos**
    * *Referência Real:* Frame cinematográfico clássico de animação consagrada em alta definição (ex: Tom & Jerry remasterizado ou clássicos Looney Tunes).
6. **`cards/series/06-series-tv.webp` — Séries TV & Produções Globais**
   * *Referência Real:* Bryan Cranston como Walter White de sobretudo e chapéu no deserto em *Breaking Bad*.
7. **`cards/series/07-series-adultos-18.webp` — Séries Adultas (+18 Restrito)**
   * *Referência Real:* Silhueta feminina artística sob contraluz azul escuro e magenta com vidro fosco molhado por vapor.

---

## 6. MANIFESTO JSON OBRIGATÓRIO (`manifest.json`)

O arquivo raiz `manifest.json` deve listar todas as mídias entregues:

```json
{
  "project": "Nexus PlayTV",
  "version": "2.0-real-cinema",
  "assets_count": {
    "banners_webp": 5,
    "banners_video_1080p": 5,
    "banners_video_720p": 5,
    "cards_filmes": 28,
    "cards_series": 7
  },
  "color_profile": "sRGB",
  "scrim_bottom_fade": "35% gradient to #0b0e0f included",
  "ai_generated": false
}
```

---

## 7. CHECKLIST DE VALIDAÇÃO ANTES DE GERAR O ZIP

* [ ] Todos os arquivos são **fotos/stills de produções REAIS** (zero arte sintética de IA).
* [ ] Nenhuma imagem tem rostos desfigurados ou gráficos genéricos.
* [ ] Os 35% inferiores de cada imagem possuem **degradê escuro suave para `#0b0e0f`**.
* [ ] Todos os vídeos MP4 estão em **loop contínuo e perfeito (sem pulo)** e sem canal de áudio.
* [ ] As imagens estão em **WebP otimizado** (entre 90 e 180 KB cada).
* [ ] Nenhuma categoria de filme ou série repete imagem de outra categoria.
* [ ] Estrutura de pastas bate 100% com o diagrama da Seção 2.
