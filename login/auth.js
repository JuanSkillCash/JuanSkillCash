(function () {
  'use strict';

  // A dónde volver tras iniciar sesión: ?next=/lo-que-sea que mandó
  // openAuthModal() en el sitio real. Solo se acepta una ruta propia del
  // sitio (empieza con "/" pero no "//", para no abrir la puerta a que un
  // link malicioso redirija a otro dominio) — cualquier otra cosa cae a "/".
  function getNextPath() {
    var raw = new URLSearchParams(window.location.search).get('next') || '/';
    if (!/^\/(?!\/)/.test(raw)) return '/';
    return raw;
  }
  var NEXT_PATH = getNextPath();

  // ============================================================
  // Conexión real a Supabase (mismo proyecto que el sitio principal).
  // ============================================================
  function translateAuthError(msg) {
    if (!msg) return 'Ocurrió un error. Intenta de nuevo.';
    if (/Token has expired or is invalid/i.test(msg)) return 'El código venció o es incorrecto. Pide uno nuevo.';
    if (/Email rate limit|For security purposes/i.test(msg)) return 'Espera un momento antes de pedir otro código.';
    if (/Signups not allowed|Email signups are disabled/i.test(msg)) return 'El registro con correo está deshabilitado en este momento.';
    if (/invalid.*email/i.test(msg)) return 'Revisa que el correo esté bien escrito.';
    return msg;
  }

  function requireClient() {
    if (!sbClient) {
      return Promise.reject(new Error('Supabase no cargó (sin conexión al CDN). Recarga la página.'));
    }
    return null;
  }

  function sendCode(email) {
    var blocked = requireClient();
    if (blocked) return blocked;
    return sbClient.auth.signInWithOtp({ email: email }).then(function (res) {
      if (res.error) throw new Error(translateAuthError(res.error.message));
      return { ok: true };
    });
  }

  function verifyCode(email, code) {
    var blocked = requireClient();
    if (blocked) return blocked;
    return sbClient.auth.verifyOtp({ email: email, token: code, type: 'email' }).then(function (res) {
      if (res.error) throw new Error(translateAuthError(res.error.message));
      return { ok: true, session: res.data && res.data.session };
    });
  }

  function loginWithGoogle() {
    var blocked = requireClient();
    if (blocked) return blocked;
    var redirectTo = window.location.origin + NEXT_PATH;
    return sbClient.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: redirectTo, queryParams: { prompt: 'select_account' } }
    }).then(function (res) {
      if (res.error) throw new Error('No se pudo iniciar con Google: ' + res.error.message);
      return { ok: true };
    });
  }

  // ============================================================
  // Estado y UI
  // ============================================================
  var card = document.getElementById('authCard');
  var states = {
    email: document.getElementById('stateEmail'),
    code: document.getElementById('stateCode'),
    success: document.getElementById('stateSuccess')
  };

  var emailForm = document.getElementById('emailForm');
  var emailInput = document.getElementById('emailInput');
  var emailError = document.getElementById('emailError');
  var btnSendCode = document.getElementById('btnSendCode');
  var btnGoogle = document.getElementById('btnGoogle');

  var codeForm = document.getElementById('codeForm');
  var codeBoxes = Array.prototype.slice.call(document.querySelectorAll('.code-box'));
  var codeError = document.getElementById('codeError');
  var btnVerifyCode = document.getElementById('btnVerifyCode');
  var btnResend = document.getElementById('btnResend');
  var btnChangeEmail = document.getElementById('btnChangeEmail');
  var resendTimerEl = document.getElementById('resendTimer');
  var codeEmailLabel = document.getElementById('codeEmailLabel');

  var currentEmail = '';
  var resendInterval = null;

  function showState(name) {
    Object.keys(states).forEach(function (k) {
      states[k].hidden = k !== name;
    });
  }

  function setLoading(btn, loading) {
    btn.classList.toggle('is-loading', loading);
    btn.disabled = loading;
  }

  function setFieldError(input, errorEl, message) {
    errorEl.textContent = message || '';
    input.classList.toggle('has-error', !!message);
  }

  function shakeCard() {
    card.classList.remove('is-shaking');
    // forzar reflow para poder reiniciar la animación
    void card.offsetWidth;
    card.classList.add('is-shaking');
  }

  // ---------- estado 1: correo ----------
  emailForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var email = emailInput.value.trim();
    setFieldError(emailInput, emailError, '');

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setFieldError(emailInput, emailError, 'Ingresa un correo válido.');
      shakeCard();
      return;
    }

    setLoading(btnSendCode, true);
    sendCode(email)
      .then(function () {
        currentEmail = email;
        codeEmailLabel.textContent = email;
        setLoading(btnSendCode, false);
        showState('code');
        resetCodeBoxes();
        startResendCountdown();
        codeBoxes[0].focus();
      })
      .catch(function (err) {
        setLoading(btnSendCode, false);
        setFieldError(emailInput, emailError, err && err.message ? err.message : 'No pudimos enviar el código. Verifica tu correo.');
        shakeCard();
      });
  });

  btnGoogle.addEventListener('click', function () {
    setLoading(btnGoogle, true);
    loginWithGoogle()
      .catch(function (err) {
        setLoading(btnGoogle, false);
        setFieldError(emailInput, emailError, err && err.message ? err.message : 'No se pudo iniciar con Google.');
        shakeCard();
      });
    // signInWithOAuth ya redirige el navegador a Google si todo sale bien;
    // no hay "then" de éxito que manejar aquí.
  });

  // ---------- estado 2: código ----------
  function resetCodeBoxes() {
    codeBoxes.forEach(function (box) { box.value = ''; });
    setFieldError(codeBoxes[0], codeError, '');
  }

  codeBoxes.forEach(function (box, i) {
    box.addEventListener('input', function () {
      box.value = box.value.replace(/[^0-9]/g, '').slice(0, 1);
      if (box.value && i < codeBoxes.length - 1) {
        codeBoxes[i + 1].focus();
      }
    });
    box.addEventListener('keydown', function (e) {
      if (e.key === 'Backspace' && !box.value && i > 0) {
        codeBoxes[i - 1].focus();
      }
    });
    box.addEventListener('paste', function (e) {
      var text = (e.clipboardData || window.clipboardData).getData('text').replace(/[^0-9]/g, '');
      if (!text) return;
      e.preventDefault();
      for (var j = 0; j < codeBoxes.length; j++) {
        codeBoxes[j].value = text[j] || '';
      }
      var lastFilled = Math.min(text.length, codeBoxes.length) - 1;
      if (lastFilled >= 0) codeBoxes[lastFilled].focus();
    });
  });

  codeForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var code = codeBoxes.map(function (b) { return b.value; }).join('');
    setFieldError(codeBoxes[0], codeError, '');

    if (code.length !== 6) {
      setFieldError(codeBoxes[0], codeError, 'Completa los 6 dígitos.');
      shakeCard();
      return;
    }

    setLoading(btnVerifyCode, true);
    verifyCode(currentEmail, code)
      .then(function () {
        setLoading(btnVerifyCode, false);
        goToSuccess();
      })
      .catch(function (err) {
        setLoading(btnVerifyCode, false);
        setFieldError(codeBoxes[0], codeError, err && err.message ? err.message : 'Código incorrecto. Intenta de nuevo.');
        shakeCard();
        resetCodeBoxes();
        codeBoxes[0].focus();
      });
  });

  function startResendCountdown() {
    var seconds = 60;
    btnResend.disabled = true;
    resendTimerEl.textContent = String(seconds);
    clearInterval(resendInterval);
    resendInterval = setInterval(function () {
      seconds -= 1;
      resendTimerEl.textContent = String(seconds);
      if (seconds <= 0) {
        clearInterval(resendInterval);
        btnResend.disabled = false;
        btnResend.textContent = 'Reenviar código';
      }
    }, 1000);
  }

  btnResend.addEventListener('click', function () {
    if (btnResend.disabled) return;
    btnResend.disabled = true;
    sendCode(currentEmail)
      .then(function () {
        btnResend.innerHTML = 'Reenviar código (<span id="resendTimer">60</span>s)';
        resendTimerEl = document.getElementById('resendTimer');
        startResendCountdown();
      })
      .catch(function (err) {
        setFieldError(codeBoxes[0], codeError, err && err.message ? err.message : 'No pudimos reenviar el código.');
        btnResend.disabled = false;
      });
  });

  btnChangeEmail.addEventListener('click', function () {
    clearInterval(resendInterval);
    showState('email');
    emailInput.focus();
  });

  // ---------- estado 3: éxito + inmersión ----------
  function goToSuccess() {
    showState('success');
    card.style.transition = 'opacity .5s ease';
    requestAnimationFrame(function () {
      card.style.opacity = '0';
    });

    var stage = window.SKC_stage;
    var map = window.SKC_getCurrentSceneMap ? window.SKC_getCurrentSceneMap() : null;
    if (stage && map) {
      var w = stage.offsetWidth, h = stage.offsetHeight;
      var cx = (map.glass.cx / 100) * w;
      var cy = (map.glass.cy / 100) * h;
      stage.style.transformOrigin = cx + 'px ' + cy + 'px';
      stage.classList.add('is-diving');
    }

    // Ya hay sesión real de Supabase en este punto: volvemos al sitio.
    // En la vista previa de Artifact (dominio claude.ai) no hay un "sitio
    // real" al que volver, así que ahí nos quedamos en la pantalla de
    // inmersión para poder juzgar la animación; en el dominio real sí
    // redirige al terminar el zoom.
    var isPreview = /\bclaude\.ai$/.test(window.location.hostname);
    if (!isPreview) {
      setTimeout(function () {
        window.location.href = NEXT_PATH;
      }, 1900);
    }
  }

  // Si llegamos aquí porque "Seguir con Google" falló en el sitio real
  // (ver checkOAuthReturnError en index.html), mostramos el motivo.
  (function showIncomingError() {
    var err = new URLSearchParams(window.location.search).get('error');
    if (err) setFieldError(emailInput, emailError, err);
  })();
})();
