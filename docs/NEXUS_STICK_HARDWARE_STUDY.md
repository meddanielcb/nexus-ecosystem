# NEXUS STICK — ESTUDO DE HARDWARE & ARQUITETURA DE DISPOSITIVOS

> Documento técnico de referência para prototipagem e fabricação OEM do dispositivo físico Nexus Stick (HDMI Plug & Play).

---

## 1. Visão Geral da Arquitetura
O dispositivo físico é um **HDMI TV Stick** com sistema Android TV aberto (AOSP) configurado em modo **Kiosk / Launcher Nativo**. Ao plugar na TV e ligar a alimentação via USB:
1. O HDMI-CEC comanda a TV para ligar e alternar para a porta do stick automaticamente.
2. O aparelho inicializa em ~15 a 20 segundos exibindo o boot logo oficial da Nexus.
3. Abre diretamente o aplicativo **Nexus PlayTV** em tela cheia (100% fullscreen, sem menus do Android ou Play Store visíveis).
4. O controle remoto Bluetooth do stick e o controle original da TV (via HDMI-CEC) controlam a navegação por D-pad (setas, OK, Voltar).

---

## 2. Engenharia de Desempenho para Grande Escala (24.000+ Itens)
Para garantir navegação a 60 FPS sem engasgos:
* **Virtualização de Tela (RecyclerView):** O stick só renderiza os 15 a 20 cards visíveis na viewport, reciclando os elementos fora da tela.
* **Banco Local Indexado (SQLite):** A lista de canais, filmes e séries é persistida localmente na memória flash do aparelho com índices textuais FTS (Full-Text Search), permitindo busca instantânea (< 3ms).
* **Cache LRU de Metadados e Imagens:** Pôsteres e capas são cacheados na memória de 16GB para carregamento local em 0.00s.
* **Decodificação por Hardware (GPU Mali-G31):** Decodificação nativa dos fluxos de vídeo em 4K@60fps sem sobrecarregar a CPU.

---

## 3. Os 2 Modelos para Prototipagem e Produção

### MODELO 1: TOP DE LINHA (Padrão Ouro — Nível BTV Cast & Firestick 4K Max)
* **Aparelho Referência:** **X98 S500 TV Stick (Amlogic S905Y4)**
* **Chipset (CPU):** Amlogic S905Y4 Quad-Core 64-bit Cortex-A35 (12nm, alta eficiência térmica)
* **GPU:** ARM Mali-G31 MP2 com suporte a Vulkan e OpenGL ES 3.2
* **Memória RAM:** 2GB LPDDR4
* **Armazenamento Interno:** 16GB eMMC 5.1
* **Codecs de Vídeo por Hardware:** **AV1 (até 4K@60fps 10-bit)**, H.265/HEVC (4K@60fps), VP9 Profile 2, HDR10+, HLG
* **Conectividade:** Wi-Fi Dual Band (2.4GHz / 5.8GHz AC MIMO) + Bluetooth 5.0
* **Sistema:** Android TV 11 / AOSP TV aberto (Root / ADB liberado para customização de ROM)
* **Controle Remoto:** Bluetooth Voice Remote com suporte HDMI-CEC
* **Consumo de Energia:** 5V / 2A via micro-USB ou USB-C (alimentável pela porta USB da maioria das TVs)
* **Custo Unitário Protótipo (AliExpress):** ~US$ 26 a US$ 32 (~R$ 145 a R$ 180)
* **Custo Atacado OEM (100 a 500 peças via Alibaba):** ~US$ 16 a US$ 19 (~R$ 90 a R$ 105)

### MODELO 2: ENTRADA / CUSTO-BENEFÍCIO (Volume e Menor Barreira de Entrada)
* **Aparelho Referência:** **Topleo 4K / T98 ATV Stick (Allwinner H618 / H313)**
* **Chipset (CPU):** Allwinner H618 Quad-Core Cortex-A53
* **GPU:** ARM Mali-G31 MP2
* **Memória RAM:** 2GB DDR3 (ou 1GB para versões ultra-econômicas)
* **Armazenamento Interno:** 8GB ou 16GB eMMC
* **Codecs de Vídeo por Hardware:** H.265/HEVC (4K@60fps), VP9, H.264 (sem decodificador de hardware para AV1)
* **Conectividade:** Wi-Fi Dual Band 2.4G/5G (suporte a Wi-Fi 6 em alguns lotes H618) + Bluetooth 5.0
* **Sistema:** Android 12 TV
* **Controle Remoto:** Infravermelho ou Bluetooth básico
* **Custo Unitário Protótipo (AliExpress):** ~US$ 14 a US$ 18 (~R$ 80 a R$ 100)
* **Custo Atacado OEM (100 a 500 peças via Alibaba):** ~US$ 8.50 a US$ 11.50 (~R$ 48 a R$ 65)

---

## 4. Comparativo Direto dos Modelos

| Critério | TOP DE LINHA (Amlogic S905Y4) | ENTRADA (Allwinner H618) |
| :--- | :--- | :--- |
| **Estabilidade Térmica** | Excelente (não perde performance sob uso contínuo) | Moderada (pode aquecer em 4K prolongado) |
| **Suporte a Codec AV1** | **Sim (Nativo por Hardware)** | Não (Apenas H.265 / H.264) |
| **Fluidez do Launcher** | 60 FPS constantes | 45-60 FPS |
| **Margem Unitária (Venda a R$ 499)** | ~R$ 390 a R$ 400 por unidade | ~R$ 430 a R$ 440 por unidade |
| **Recomendação de Uso** | Produto Principal (Carro-Chefe Nexus) | Linha Light / Promocional |

---

## 5. Roteiro para Fabricação Própria (Shenzhen OEM / ODM)
1. **Fase 1 (Protótipo):** Comprar 1 unidade de cada modelo via AliExpress para validar temperatura, resposta do controle e auto-boot.
2. **Fase 2 (Customização de ROM):** Fornecer o pacote de boot (logo Nexus em verde neon + APK compilado como app do sistema em `/system/priv-app/`).
3. **Fase 3 (Silk e Embalagem):** Fabricante grava o emblema Nexus na carcaça preta e no controle remoto (pedido mínimo geralmente entre 200 e 500 unidades).
