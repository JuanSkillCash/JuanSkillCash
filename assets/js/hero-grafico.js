/* Fondo animado del hero, detras del tiburon y el titulo: en vez de copiar el grafico de
 * precio tipo bursatil de la referencia (cryptobruj.com), esto son "corrientes" tipo sonar/agua
 * que fluyen solas y se apartan del cursor como una onda en el agua - encaja con el tema
 * tiburon/oceano del sitio en vez del tema "grafico de trading". Pausa fuera de pantalla,
 * respeta prefers-reduced-motion, DPR maximo 2.
 */
(function(){
  var contenedor = document.querySelector('.hero-mascot');
  if(!contenedor || !window.requestAnimationFrame) return;
  var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var canvas = document.createElement('canvas');
  canvas.className = 'hero-grafico';
  canvas.setAttribute('aria-hidden', 'true');
  contenedor.insertBefore(canvas, contenedor.firstChild);
  var ctx = canvas.getContext('2d');
  if(!ctx) return;

  var colorHex = getComputedStyle(contenedor).getPropertyValue('--hero-grafico-color').trim() || '#ff2f4f';
  function rgba(a){
    var hex = colorHex.replace('#', '');
    var n = parseInt(hex, 16);
    return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  var W = 0, H = 0, visible = true;
  var m = { x: -9999, y: -9999, tx: -9999, ty: -9999, f: 0, tf: 0 };

  function medir(){
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var r = contenedor.getBoundingClientRect();
    W = r.width; H = r.height;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // "corrientes" - cada una con su propia altura base, amplitud, velocidad y fase
  var LINEAS = [
    { base: .30, amp: 14, vel: .00042, fase: 0,   grosor: 1.4, op: .50 },
    { base: .48, amp: 20, vel: .00031, fase: 1.7, grosor: 1.8, op: .65 },
    { base: .64, amp: 16, vel: .00052, fase: 3.4, grosor: 1.4, op: .45 },
    { base: .80, amp: 10, vel: .00038, fase: 5.1, grosor: 1.2, op: .35 }
  ];
  var PASO = 6;
  var R_DISTORSION = 140;

  function dibujar(ts){
    ctx.clearRect(0, 0, W, H);

    LINEAS.forEach(function(L){
      ctx.beginPath();
      var primero = true;
      for(var x = -PASO; x <= W + PASO; x += PASO){
        var y = L.base * H + Math.sin(x * 0.012 + ts * L.vel + L.fase) * L.amp;
        if(m.f > 0.02){
          var dx = x - m.x, dy = y - m.y;
          var dist = Math.hypot(dx, dy);
          if(dist < R_DISTORSION){
            var fuerza = (1 - dist / R_DISTORSION) * 26 * m.f;
            var ang = Math.atan2(dy, dx);
            y -= Math.sin(ang) * fuerza;
          }
        }
        if(primero){ ctx.moveTo(x, y); primero = false; } else { ctx.lineTo(x, y); }
      }
      ctx.strokeStyle = rgba(L.op);
      ctx.lineWidth = L.grosor;
      ctx.lineJoin = 'round';
      ctx.stroke();
    });

    // ping de sonar: late solo, en una esquina del hero
    var px = W * 0.86, py = H * 0.28;
    var pulso = (Math.sin(ts / 900) + 1) / 2;
    ctx.strokeStyle = rgba(.35 * (1 - pulso));
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(px, py, 6 + pulso * 22, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = rgba(.8);
    ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();
  }

  function pintar(ts){
    if(!visible) return;
    m.x += (m.tx - m.x) * 0.12; m.y += (m.ty - m.y) * 0.12; m.f += (m.tf - m.f) * 0.08;
    dibujar(ts);
    if(!reduceMotion) requestAnimationFrame(pintar);
  }

  function mover(x, y){
    var r = contenedor.getBoundingClientRect();
    m.tx = x - r.left; m.ty = y - r.top; m.tf = 1;
    if(m.x < -999){ m.x = m.tx; m.y = m.ty; }
  }
  if(!reduceMotion){
    contenedor.addEventListener('pointermove', function(e){ if(e.pointerType !== 'touch') mover(e.clientX, e.clientY); });
    contenedor.addEventListener('pointerleave', function(){ m.tf = 0; });
  }
  addEventListener('resize', medir);

  if('IntersectionObserver' in window){
    new IntersectionObserver(function(es){
      var vv = es[0].isIntersecting;
      if(vv && !visible){ visible = true; requestAnimationFrame(pintar); }
      else if(!vv) visible = false;
    }).observe(contenedor);
  }

  medir();
  pintar(0);
})();
