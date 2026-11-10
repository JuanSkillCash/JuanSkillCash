/* Efectos "Magic Bento" en las cajas de la pagina principal (.cat-overview-card): borde que
 * se ilumina donde esta el mouse, inclinacion 3D leve al pasar por encima, una ondita al hacer
 * click, y una lineita de "grafico" (dato inventado, no son precios reales) que se dibuja al
 * pasar el mouse. Inspirado en cryptobruj.com/exchanges pero con nuestro --accent unico (nada
 * de paleta nueva por tarjeta).
 *
 * (Hubo tambien un foco/resplandor que seguia el cursor por toda la seccion - Juan pidio
 * quitarlo, ver historial de commits. El tilt/glow/linea de aqui NUNCA fueron parte de esa
 * queja, se quedan igual que siempre.)
 *
 * El tilt/glow/linea solo corren en escritorio con mouse real y nunca si el usuario pidio
 * menos movimiento (prefers-reduced-motion). La ondita de click si corre en cualquier
 * dispositivo.
 */
(function(){
  var tarjetas = [].slice.call(document.querySelectorAll('.cat-overview-card'));
  if(!tarjetas.length) return;

  var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hoverFino = matchMedia('(hover: hover) and (pointer: fine)').matches;

  // lineita decorativa tipo "grafico" en el tercio inferior de cada caja - paseo aleatorio
  // reproducible (mismo generador congruencial lineal sembrado por el indice de la tarjeta),
  // oculta de entrada; solo "se dibuja" si hay hover (ver mas abajo, clase mg-viva)
  var NS = 'http://www.w3.org/2000/svg';
  tarjetas.forEach(function(t, i){
    var pts = [];
    var y = 60, s = i * 7 + 3;
    for(var x = 0; x <= 100; x += 5){
      s = (s * 9301 + 49297) % 233280;
      y = Math.max(14, Math.min(90, y + (s / 233280 - 0.52) * 24));
      pts.push([x, y]);
    }
    var p = pts.map(function(q, k){ return (k ? 'L' : 'M') + q[0] + ' ' + q[1]; }).join(' ');
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'mg-linea');
    svg.setAttribute('viewBox', '0 0 100 100');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    var id = 'mg-area-' + i;
    svg.innerHTML = '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="currentColor" stop-opacity=".22"/>' +
      '<stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>' +
      '<path class="area" fill="url(#' + id + ')" d="' + p + ' L100 100 L0 100 Z"/><path d="' + p + '"/>';
    t.appendChild(svg);
    var linea = svg.lastElementChild;
    var L = linea.getTotalLength();
    linea.style.strokeDasharray = L;
    linea.style.strokeDashoffset = L;
  });

  tarjetas.forEach(function(t){
    t.addEventListener('click', function(e){
      if(reduceMotion) return;
      if(e.target.closest('a, button[data-tool], label, input, code')) return;
      var c = t.getBoundingClientRect();
      var o = document.createElement('i');
      o.className = 'mg-onda';
      o.style.left = (e.clientX - c.left) + 'px';
      o.style.top = (e.clientY - c.top) + 'px';
      t.appendChild(o);
      setTimeout(function(){ o.remove(); }, 900);
    });
  });

  if(reduceMotion || !hoverFino) return;

  var raf = null;
  var ultimo = null;

  // el botoncito de girar vive fuera de .cat-flip-inner (para nunca voltearse junto con la
  // tarjeta) - eso lo dejaba quieto mientras la tarjeta se inclinaba con el mouse, como flotando
  // aparte ("mundo aparte", reporte de Juan). Se precalcula aqui (una sola vez) el par
  // outer/toggle de cada tarjeta para copiarle la misma inclinacion mas abajo, sin tener que
  // buscarlo en el DOM en cada cuadro de animacion.
  var outers = tarjetas.map(function(t){ return t.closest('.cat-flip-outer'); });
  var toggles = outers.map(function(outer){ return outer ? outer.querySelector(':scope > .cat-flip-toggle') : null; });

  // en vez de pointerenter/pointerleave (que con el tilt 3D se confundian solos y se quedaban
  // "pegados" en false para siempre) calculamos cada cuadro, con la posicion real del mouse,
  // si esta encima de cada tarjeta - se autocorrige cada frame, nunca se puede quedar trabado
  function actualizar(){
    raf = null;
    var e = ultimo;
    if(!e) return;

    tarjetas.forEach(function(t, i){
      var toggle = toggles[i];
      var c = t.getBoundingClientRect();
      var encima = e.clientX >= c.left && e.clientX <= c.right && e.clientY >= c.top && e.clientY <= c.bottom;
      t.classList.toggle('mg-viva', encima);
      if(encima){
        var x = (e.clientX - c.left) / c.width - 0.5;
        var y = (e.clientY - c.top) / c.height - 0.5;
        // sin perspective() propio: la tarjeta ya vive dentro de .cat-flip-outer, que trae su
        // propio perspective - anidar un segundo perspective() aqui confundia el hit-testing
        var inclinacion = 'rotateX(' + (-y * 6).toFixed(2) + 'deg) rotateY(' +
          (x * 6).toFixed(2) + 'deg) translate(' + (x * 8).toFixed(1) + 'px,' + (y * 8).toFixed(1) + 'px)';
        // el translateZ va SOLO aqui, mientras se esta inclinando - no como propiedad fija en el
        // CSS (eso se probo y se revirtio: dejaba la tarjeta borrosa todo el tiempo, no solo al
        // pasar el mouse, por la capa 3D que arma Chrome con el zoom de Windows en 125%).
        // Empuja la cara del frente delante del plano de .cat-flip-inner para que el clic no le
        // caiga a el en vez de al boton cuando la tarjeta esta inclinada.
        t.style.transform = 'translateZ(30px) ' + inclinacion + ' translateY(-2px)';
        // mismo giro para el botoncito de voltear (sin el translateZ, que no le hace falta a
        // el) para que se sienta pegado a la caja en vez de quieto aparte; si la tarjeta esta
        // volteada se le mantiene el rotate(180deg) de siempre, sumado a la inclinacion
        if(toggle) toggle.style.transform = (outers[i].classList.contains('flipped') ? 'rotate(180deg) ' : '') + inclinacion;
        t.style.setProperty('--glow-x', ((e.clientX - c.left) / c.width * 100).toFixed(1) + '%');
        t.style.setProperty('--glow-y', ((e.clientY - c.top) / c.height * 100).toFixed(1) + '%');
        t.style.setProperty('--glow-i', '1');
      } else {
        t.style.transform = '';
        if(toggle) toggle.style.transform = '';
        t.style.setProperty('--glow-i', '0');
      }
    });
  }

  document.addEventListener('pointermove', function(e){
    ultimo = e;
    if(raf == null) raf = requestAnimationFrame(actualizar);
  });
})();
