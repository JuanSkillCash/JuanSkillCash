(function () {
  'use strict';

  var SCENE_MAP = {
    desktop: {
      minWidth: 721,
      w: 1920, h: 1080,
      ring: { cx: 39.6, cy: 45.0, r: 23.3 },
      glass: { cx: 39.6, cy: 45.0, r: 21.6 }
    },
    mobile: {
      minWidth: 0,
      w: 832, h: 1152,
      ring: { cx: 41.5, cy: 30.9, r: 35.7 },
      glass: { cx: 41.5, cy: 30.9, r: 33.0 }
    }
  };

  var RING_MARGIN = 1.04;       // anillo + ~4% de margen, siempre visible
  var CARD_GAP = 32;            // separación mínima tarjeta-anillo
  var CARD_EDGE_MARGIN = 32;    // margen de la tarjeta al borde de la pantalla
  var CARD_MAX_W = 420;
  var CARD_MIN_W = 380;

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var stage = document.getElementById('stage');
  var sceneImg = document.getElementById('sceneImg');
  var glassLayers = document.getElementById('glassLayers');
  var ringGlow = document.getElementById('ringGlow');
  var spillLight = document.getElementById('spillLight');

  var current = SCENE_MAP.desktop;
  var rafId = null;
  var visible = !document.hidden;

  function currentMap() {
    return window.innerWidth <= 720 ? SCENE_MAP.mobile : SCENE_MAP.desktop;
  }

  function setVars(map) {
    var root = document.documentElement.style;
    root.setProperty('--ring-cx', map.ring.cx + '%');
    root.setProperty('--ring-cy', map.ring.cy + '%');
    root.setProperty('--ring-r', map.ring.r + '%');
    root.setProperty('--glass-r', map.glass.r + '%');
  }

  // Escala que garantiza que el anillo (+ margen) siempre quepa en la
  // ventana, sin importar qué tan distinto sea su aspect ratio al de
  // la imagen — evita que "cover" recorte la portilla en pantallas
  // muy anchas o muy angostas.
  function fitRingScale(map, vw, vh) {
    var ringRadiusNative = (map.ring.r / 100) * map.w;
    var requiredRadius = ringRadiusNative * RING_MARGIN;
    var cxNative = (map.ring.cx / 100) * map.w;
    var cyNative = (map.ring.cy / 100) * map.h;
    var halfW = map.w / 2, halfH = map.h / 2;
    var denomX = 2 * (requiredRadius + Math.abs(halfW - cxNative));
    var denomY = 2 * (requiredRadius + Math.abs(halfH - cyNative));
    return Math.min(vw / denomX, vh / denomY);
  }

  function sizeStage() {
    var map = currentMap();
    current = map;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var scaleCover = Math.max(vw / map.w, vh / map.h);
    var scale = Math.min(scaleCover, fitRingScale(map, vw, vh));
    var w = Math.ceil(map.w * scale);
    var h = Math.ceil(map.h * scale);
    stage.style.width = w + 'px';
    stage.style.height = h + 'px';

    setVars(map);

    var glassCx = (map.glass.cx / 100) * w;
    var glassCy = (map.glass.cy / 100) * h;
    var glassR = (map.glass.r / 100) * w;
    glassLayers.style.clipPath = 'circle(' + glassR + 'px at ' + glassCx + 'px ' + glassCy + 'px)';
    glassLayers.style.webkitClipPath = glassLayers.style.clipPath;

    layoutCard(map, w, h, vw, vh);
  }

  // Desplaza la escena y/o encoge la tarjeta para que nunca se toquen.
  function layoutCard(map, stageW, stageH, vw, vh) {
    var isDesktop = vw > 720;
    if (!isDesktop) {
      stage.style.left = '';
      document.documentElement.style.setProperty('--card-max-w', CARD_MAX_W + 'px');
      return;
    }

    var ringCx = (map.ring.cx / 100) * stageW;
    var ringR = (map.ring.r / 100) * stageW;
    var stageLeft = (vw - stageW) / 2; // centrado, antes de cualquier desplazamiento
    var ringRightViewport = stageLeft + ringCx + ringR;

    var availableForCard = vw - CARD_EDGE_MARGIN - CARD_GAP - ringRightViewport;
    var cardWidth, offsetX = 0;

    if (availableForCard >= CARD_MAX_W) {
      cardWidth = CARD_MAX_W;
    } else if (availableForCard >= CARD_MIN_W) {
      cardWidth = availableForCard;
    } else {
      cardWidth = CARD_MIN_W;
      offsetX = -(CARD_MIN_W - availableForCard);
    }

    stage.style.left = 'calc(50% + ' + offsetX + 'px)';
    document.documentElement.style.setProperty('--card-max-w', Math.round(cardWidth) + 'px');
  }

  // ---------- parallax ----------
  var parallaxX = 0, parallaxY = 0, targetX = 0, targetY = 0;

  function onMouseMove(e) {
    if (reduceMotion) return;
    var w = window.innerWidth, h = window.innerHeight;
    targetX = ((e.clientX / w) - 0.5) * -10;
    targetY = ((e.clientY / h) - 0.5) * -8;
  }

  function onDeviceOrientation(e) {
    if (reduceMotion || e.gamma == null) return;
    targetX = Math.max(-10, Math.min(10, e.gamma * 0.4));
    targetY = Math.max(-8, Math.min(8, (e.beta - 45) * 0.25));
  }

  function parallaxLoop() {
    parallaxX += (targetX - parallaxX) * 0.06;
    parallaxY += (targetY - parallaxY) * 0.06;
    glassLayers.style.transform = 'translate(' + parallaxX.toFixed(2) + 'px,' + parallaxY.toFixed(2) + 'px)';
  }

  // ---------- loop principal ----------
  function loop() {
    if (!visible) { rafId = null; return; }
    parallaxLoop();
    rafId = requestAnimationFrame(loop);
  }

  function startLoop() {
    if (rafId == null) {
      visible = true;
      rafId = requestAnimationFrame(loop);
    }
  }
  function stopLoop() {
    visible = false;
    if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stopLoop(); else startLoop();
  });

  window.addEventListener('resize', sizeStage);
  window.addEventListener('orientationchange', sizeStage);
  if (!reduceMotion) {
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    if (window.DeviceOrientationEvent && 'ontouchstart' in window) {
      window.addEventListener('deviceorientation', onDeviceOrientation, { passive: true });
    }
  }

  sizeStage();
  startLoop();

  window.SKC_SCENE_MAP = SCENE_MAP;
  window.SKC_getCurrentSceneMap = function () { return current; };
  window.SKC_stage = stage;
})();
