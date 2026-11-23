(function () {
  'use strict';

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var headerLogo = document.getElementById('headerLogo');
  var cardLogo = document.getElementById('cardLogo');

  function inject(target, svgText) {
    if (target) target.innerHTML = svgText;
  }

  function showCard() {
    document.querySelectorAll('.auth-card').forEach(function (c) {
      c.classList.add('is-visible');
    });
  }

  fetch('assets/logo.svg')
    .then(function (r) { return r.text(); })
    .then(function (svgText) {
      inject(headerLogo, svgText);
      inject(cardLogo, svgText);
    })
    .catch(function () {
      // Si falla la carga (p.ej. file://), igual mostramos la tarjeta.
    })
    .then(function () {
      if (reduceMotion) { showCard(); return; }
      setTimeout(showCard, 250);
    });
})();
