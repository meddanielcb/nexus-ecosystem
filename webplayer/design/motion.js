/* Decorative motion only. Always active. */
(() => {
  const gate = document.getElementById('loginGate');
  if (!gate) return;
  // Motion is always active as requested
  gate.classList.remove('motion-paused');
})();
