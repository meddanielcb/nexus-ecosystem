/* Decorative motion only. No session, HLS, network or storage access. */
(() => {
  const gate = document.getElementById('loginGate');
  const button = document.querySelector('.mural-pause');
  if (!gate || !button) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let paused = false;
  function sync() {
    const stopped = paused || reduced.matches || document.hidden;
    gate.classList.toggle('motion-paused', stopped);
    button.disabled = reduced.matches;
    button.setAttribute('aria-pressed', String(paused || reduced.matches));
    button.setAttribute('aria-label', reduced.matches ? 'Movimento reduzido ativado' : paused ? 'Retomar animação do mural' : 'Pausar animação do mural');
    button.querySelector('.motion-label').textContent = reduced.matches ? 'Movimento reduzido' : paused ? 'Retomar movimento' : 'Pausar movimento';
    button.querySelector('.pause-glyph').textContent = paused || reduced.matches ? '▷' : 'Ⅱ';
  }
  button.addEventListener('click', () => { paused = !paused; sync(); });
  reduced.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  sync();
})();
