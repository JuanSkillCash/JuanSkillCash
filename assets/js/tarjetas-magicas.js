/* Efectos "Magic Bento" en las cajas de la pagina principal (.cat-overview-card): borde que
 * se ilumina donde esta el mouse, foco que sigue el cursor por la pantalla, inclinacion 3D
 * leve al pasar por encima, y una ondita al hacer click. Inspirado en cryptobruj.com/exchanges
 * pero con nuestro --accent unico (nada de paleta nueva por tarjeta).
 *
 * El tilt/glow/foco solo corren en escritorio con mouse real y nunca si el usuario pidio menos
 * movimiento (prefers-reduced-motion). La ondita de click si corre en cualquier dispositivo.
 */
(function(){
  var tarjetas = [].slice.call(document.querySelectorAll('.cat-overview-card'));
  if(!tarjetas.length) return;

  var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hoverFino = matchMedia('(hover: hover) and (pointer: fine)').matches;

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

  var foco = document.createElement('div');
  foco.className = 'mg-foco';
  foco.setAttribute('aria-hidden', 'true');
  document.body.appendChild(foco);

  var R = 300;
  var raf = null;
  var ultimo = null;

  function actualizar(){
    raf = null;
    var e = ultimo;
    if(!e) return;
    var dentro = tarjetas.some(function(t){
      var b = t.getBoundingClientRect();
      return e.clientX > b.left - R && e.clientX < b.right + R && e.clientY > b.top - R && e.clientY < b.bottom + R;
    });
    foco.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)';
    foco.style.opacity = dentro ? '1' : '0';

    tarjetas.forEach(function(t){
      var c = t.getBoundingClientRect();
      var dx = Math.max(c.left - e.clientX, 0, e.clientX - c.right);
      var dy = Math.max(c.top - e.clientY, 0, e.clientY - c.bottom);
      var dist = Math.hypot(dx, dy);
      var i = dist > R ? 0 : 1 - dist / R;
      t.style.setProperty('--glow-x', ((e.clientX - c.left) / c.width * 100).toFixed(1) + '%');
      t.style.setProperty('--glow-y', ((e.clientY - c.top) / c.height * 100).toFixed(1) + '%');
      t.style.setProperty('--glow-i', i.toFixed(2));
    });
  }

  document.addEventListener('pointermove', function(e){
    ultimo = e;
    if(raf == null) raf = requestAnimationFrame(actualizar);
  });

  tarjetas.forEach(function(t){
    t.addEventListener('pointermove', function(e){
      var c = t.getBoundingClientRect();
      var x = (e.clientX - c.left) / c.width - 0.5;
      var y = (e.clientY - c.top) / c.height - 0.5;
      t.style.transform = 'perspective(1000px) rotateX(' + (-y * 6).toFixed(2) + 'deg) rotateY(' +
        (x * 6).toFixed(2) + 'deg) translate(' + (x * 8).toFixed(1) + 'px,' + (y * 8).toFixed(1) +
        'px) translateY(-2px)';
    });
    t.addEventListener('pointerenter', function(){ t.classList.add('mg-viva'); });
    t.addEventListener('pointerleave', function(){
      t.classList.remove('mg-viva');
      t.style.transform = '';
    });
  });
})();
