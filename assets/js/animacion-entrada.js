/* Animacion de entrada al cargar la pagina: el titulo del hero aparece letra por letra y las
 * 7 cajas de la pagina principal entran en cascada (una detras de otra). Es puramente
 * decorativo y corre una sola vez; si el usuario pidio menos movimiento
 * (prefers-reduced-motion) no se toca nada y todo se ve normal de inmediato.
 */
(function(){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  function partir(nodo, modo){
    var i = 0;
    [].slice.call(nodo.childNodes).forEach(function(n){
      if(n.nodeType !== 3){
        if(n.nodeType === 1){ n.classList.add('sp'); n.style.setProperty('--i', i++); }
        return;
      }
      var frag = document.createDocumentFragment();
      n.textContent.split(/(\s+)/).forEach(function(parte){
        if(!parte) return;
        if(/^\s+$/.test(parte)){ frag.appendChild(document.createTextNode(' ')); return; }
        var w = document.createElement('span');
        w.className = 'sw';
        if(modo === 'chars'){
          [].slice.call(parte).forEach(function(ch){
            var c = document.createElement('span');
            c.className = 'sp';
            c.textContent = ch;
            c.style.setProperty('--i', i++);
            w.appendChild(c);
          });
        } else {
          w.classList.add('sp');
          w.textContent = parte;
          w.style.setProperty('--i', i++);
        }
        frag.appendChild(w);
      });
      nodo.replaceChild(frag, n);
    });
    nodo.classList.add('split');
  }

  document.documentElement.classList.add('split-js');

  var titulo = document.querySelector('.hero-mascot-title');
  if(titulo && !titulo.getAttribute('aria-label')){
    titulo.setAttribute('aria-label', titulo.textContent);
    partir(titulo, 'chars');
    // el <script> inline justo despues del <h1> en el HTML lo escondio de una con esta clase
    // (pre-split) para que no se alcance a ver completo antes de separarlo en letras - ya
    // separado, se quita: cada letra (.sp) ya trae su propia animacion de entrada
    titulo.classList.remove('pre-split');
  }

  var idx = 0;
  document.querySelectorAll('.cat-flip-outer').forEach(function(outer){
    outer.style.setProperty('--i', idx++);
  });
})();
