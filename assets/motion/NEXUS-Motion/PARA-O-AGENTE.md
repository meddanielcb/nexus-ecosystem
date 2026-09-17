# NEXUS Motion

- nexus-orbita-luz.mp4: versão principal, 720×720, H.264, 30fps, 6s, sem áudio. Pulsação suave e luz em trajetória orbital. Base é o avatar orbital aprovado; não é uma reconstrução 3D dos elementos.
- nexus-orbital-perfil.mp4: alternativa discreta, apenas pulsação/zoom lento.
- nexus-loader.svg: animação vetorial transparente, símbolo geométrico original, arco girando em 5s e respiração em 3s. CSS interno desativa animações em prefers-reduced-motion. Usar no carregamento real, sem impor atraso artificial.
- previa.html: comparação com controle de pausa. Abra servido por HTTP local para controle do SVG incorporado; file:// pode impedir o botão de controlar o SVG por política do navegador. A regra de reduced-motion do SVG continua independente.

PWA: manter os PNGs estáticos do kit no manifesto e na tela inicial do sistema. A animação pertence à interface após o carregamento da página; a splash nativa é controlada pelo sistema. No app, preferir SVG inline com role=img/aria-label e status textual separado; ocultar o loader quando a operação terminar. Não inferir progresso de uma animação indeterminada. Pausar quando fora de tela ou aba oculta. Não usar GIF como loader principal.

Telegram: vídeo para perfil onde o cliente disponibiliza essa opção; selecionar um frame como foto estática. Não foi testado upload em conta, bot ou canal; essas superfícies podem ter recursos diferentes. Nenhum perfil foi alterado.
https://telegram.org/blog/profile-videos-people-nearby-and-more
https://web.dev/learn/pwa/web-app-manifest

Validação: arquivos de vídeo decodificados, duração/dimensões verificadas, frames inspecionados e SVG analisado como XML. Não foi realizado teste em dispositivo nem no navegador. Não publicado. Este pacote complementa o kit existente e não modifica o projeto.
