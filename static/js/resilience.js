/* ════════════════════════════════════════════════════════════════
   COR AMANS — Resilience JS
   Page loader · Skeleton screens · Offline/slow detection ·
   Form loading states · Image lazy-load · Auto-retry · Error UI
════════════════════════════════════════════════════════════════ */
(function (w, d) {
  'use strict';

  /* ── Helpers ─────────────────────────────────────────── */
  function $(sel, ctx) { return (ctx || d).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || d).querySelectorAll(sel)); }

  /* ── 1. PAGE LOAD PROGRESS BAR ───────────────────────── */
  var loader = null;
  var loaderTimer = null;

  function createLoader() {
    if (loader) return;
    loader = d.createElement('div');
    loader.id = 'page-loader';
    d.body.insertBefore(loader, d.body.firstChild);
  }

  function startLoader() {
    createLoader();
    loader.classList.remove('done', 'indeterminate');
    loader.style.width = '0%';
    // Short delay then go indeterminate (most pages render fast)
    loaderTimer = setTimeout(function () {
      loader.classList.add('indeterminate');
    }, 120);
  }

  function finishLoader() {
    if (!loader) return;
    clearTimeout(loaderTimer);
    loader.classList.remove('indeterminate');
    loader.classList.add('done');
    setTimeout(function () { loader.style.width = '0%'; }, 450);
  }

  // Start on nav clicks
  d.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript') ||
        href.startsWith('mailto') || href.startsWith('tel') ||
        a.getAttribute('target') === '_blank' || e.ctrlKey || e.metaKey) return;
    startLoader();
  });

  // Finish when page fully painted
  w.addEventListener('load', finishLoader);
  d.addEventListener('DOMContentLoaded', function () {
    finishLoader();
    d.body.classList.add('content-ready');
  });

  /* ── 2. NETWORK STATUS DETECTION ─────────────────────── */
  var banner    = null;
  var bannerTO  = null;
  var wasOffline = false;

  function ensureBanner() {
    if (banner) return;
    banner = d.createElement('div');
    banner.id = 'connection-banner';
    banner.innerHTML =
      '<div class="conn-banner-inner">' +
        '<i class="fas fa-wifi" id="conn-icon"></i>' +
        '<span id="conn-msg"></span>' +
        '<button class="conn-dismiss" aria-label="Dismiss">' +
          '<i class="fas fa-xmark"></i>' +
        '</button>' +
      '</div>';
    d.body.appendChild(banner);
    banner.querySelector('.conn-dismiss').addEventListener('click', hideBanner);
  }

  function showBanner(type, icon, msg) {
    ensureBanner();
    clearTimeout(bannerTO);
    banner.className = type;
    $('#conn-icon', banner).className = 'fas ' + icon;
    d.getElementById('conn-msg').innerHTML = msg;
    requestAnimationFrame(function () { banner.classList.add('visible'); });
  }

  function hideBanner(delay) {
    if (!banner) return;
    clearTimeout(bannerTO);
    bannerTO = setTimeout(function () {
      banner.classList.remove('visible');
    }, delay || 0);
  }

  function goOffline() {
    wasOffline = true;
    d.body.setAttribute('data-offline', '');
    // Show inline banner; clicking the reload link goes to /offline page
    showBanner('offline', 'fa-wifi-slash',
      'You\'re offline — some features unavailable. <a href="/offline" style="color:inherit;text-decoration:underline;">Offline info</a>');
    updateNetDot('offline');
  }

  function goOnline() {
    d.body.removeAttribute('data-offline');
    if (wasOffline) {
      showBanner('back-online', 'fa-circle-check',
        'You\'re back online.');
      hideBanner(3500);
    }
    wasOffline = false;
    updateNetDot('good');
  }

  w.addEventListener('offline', goOffline);
  w.addEventListener('online',  goOnline);
  if (!navigator.onLine) goOffline();

  /* ── 3. SLOW CONNECTION DETECTION ────────────────────── */
  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

  function checkConnectionQuality() {
    if (!conn) return;
    var type = conn.effectiveType;
    if (type === 'slow-2g' || type === '2g') {
      showBanner('slow', 'fa-gauge-simple-low',
        'Slow connection detected. Pages may take longer to load.');
      hideBanner(6000);
      d.body.setAttribute('data-slow-conn', '');
      updateNetDot('poor');
    } else if (type === '3g') {
      updateNetDot('slow');
    } else {
      d.body.removeAttribute('data-slow-conn');
      updateNetDot('good');
    }
  }

  if (conn) {
    conn.addEventListener('change', checkConnectionQuality);
    checkConnectionQuality();
  }

  // Probe-based: measure actual fetch latency
  function probeLatency() {
    if (!navigator.onLine) return;
    var t0 = performance.now();
    fetch('/health', { cache: 'no-store', method: 'GET' })
      .then(function () {
        var ms = performance.now() - t0;
        if (ms > 3000) {
          d.body.setAttribute('data-slow-conn', '');
          updateNetDot('poor');
        } else if (ms > 1200) {
          updateNetDot('slow');
        } else {
          d.body.removeAttribute('data-slow-conn');
          updateNetDot('good');
        }
      })
      .catch(function () { /* offline event will fire */ });
  }
  // Probe once on load, then every 90 seconds
  w.addEventListener('load', function () {
    setTimeout(probeLatency, 2000);
    setInterval(probeLatency, 90000);
  });

  /* ── 4. NET QUALITY DOT ──────────────────────────────── */
  function updateNetDot(level) {
    var dot = d.getElementById('net-quality');
    if (!dot) return;
    dot.className = '';
    if (level !== 'good') dot.classList.add(level);
  }

  /* ── 5. FORM LOADING STATES ──────────────────────────── */
  d.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.dataset.noloading) return;

    // Mark form as submitting
    form.classList.add('form-submitting');

    // Find the submit button and add spinner
    var btn = form.querySelector('[type="submit"]');
    if (btn && !btn.dataset.noloading) {
      var origText = btn.innerHTML;
      btn.classList.add('btn-loading');
      btn.innerHTML = '<span class="btn-text">' + origText + '</span>';
      btn.disabled = true;
      // Restore after 12s as a safety fallback
      setTimeout(function () {
        btn.classList.remove('btn-loading');
        btn.innerHTML = origText;
        btn.disabled = false;
        form.classList.remove('form-submitting');
      }, 12000);
    }
  });

  // Also handle AJAX forms (non-nav fetch calls)
  var origFetch = w.fetch;
  w.fetch = function () {
    startLoader();
    return origFetch.apply(this, arguments).then(
      function (r) { finishLoader(); return r; },
      function (e) { finishLoader(); throw e; }
    );
  };

  /* ── 6. LAZY IMAGE LOADING ───────────────────────────── */
  function lazyLoad() {
    var imgs = $$('img[data-src]');
    if (!imgs.length) return;

    if ('IntersectionObserver' in w) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          loadImg(entry.target);
          io.unobserve(entry.target);
        });
      }, { rootMargin: '200px' });
      imgs.forEach(function (img) { io.observe(img); });
    } else {
      imgs.forEach(loadImg); // fallback
    }
  }

  function loadImg(img) {
    img.classList.add('lazy-img');
    var src = img.dataset.src;
    if (!src) return;
    var tmp = new Image();
    tmp.onload = function () {
      img.src = src;
      img.removeAttribute('data-src');
      img.classList.add('loaded');
      var wrap = img.closest('.img-wrap');
      if (wrap) wrap.classList.add('loaded');
    };
    tmp.onerror = function () {
      img.classList.add('error');
      var wrap = img.closest('.img-wrap');
      if (wrap) wrap.classList.add('error');
    };
    tmp.src = src;
  }

  d.addEventListener('DOMContentLoaded', lazyLoad);

  /* ── 7. AUTO-RETRY FETCH WRAPPER ─────────────────────── */
  w.fetchWithRetry = function (url, opts, maxRetries) {
    var retries = maxRetries !== undefined ? maxRetries : 3;
    var delay   = 1000;

    function attempt(n) {
      return origFetch(url, opts).then(function (r) {
        if (!r.ok && r.status >= 500 && n < retries) {
          return new Promise(function (res) { setTimeout(res, delay * n); })
                 .then(function () { return attempt(n + 1); });
        }
        return r;
      }).catch(function (err) {
        if (n < retries) {
          return new Promise(function (res) { setTimeout(res, delay * n); })
                 .then(function () { return attempt(n + 1); });
        }
        throw err;
      });
    }
    return attempt(1);
  };

  /* ── 8. SKELETON → CONTENT SWAP ──────────────────────── */
  // Any element with data-skeleton="loading" gets skeleton treatment
  // until the server sends data-skeleton="done" (for AJAX sections)
  // or until DOMContentLoaded fires (for SSR).
  d.addEventListener('DOMContentLoaded', function () {
    $$('[data-skeleton]').forEach(function (el) {
      el.dataset.skeleton = 'done';
      el.classList.remove('is-skeleton');
    });
  });

  /* ── 9. RETRY UI COMPONENT ───────────────────────────── */
  // Usage: <div data-retry-url="/api/resources" data-retry-target="#content"></div>
  d.addEventListener('DOMContentLoaded', function () {
    $$('[data-retry-url]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var targetSel = btn.dataset.retryTarget;
        var url       = btn.dataset.retryUrl;
        if (!url) return;
        startLoader();
        btn.disabled = true;
        btn.textContent = 'Retrying…';
        origFetch(url)
          .then(function (r) { return r.text(); })
          .then(function (html) {
            if (targetSel) {
              var target = d.querySelector(targetSel);
              if (target) target.innerHTML = html;
            }
            finishLoader();
          })
          .catch(function () {
            finishLoader();
            btn.disabled = false;
            btn.textContent = 'Retry';
          });
      });
    });
  });

  /* ── 10. COUNTDOWN RETRY ─────────────────────────────── */
  // Usage: <button data-countdown="5" data-countdown-action="reload">
  //          Retrying in <span class="countdown-num">5</span>s
  //        </button>
  d.addEventListener('DOMContentLoaded', function () {
    $$('[data-countdown]').forEach(function (el) {
      var total  = parseInt(el.dataset.countdown, 10) || 10;
      var num    = el.querySelector('.countdown-num');
      var action = el.dataset.countdownAction || 'reload';
      var count  = total;

      var iv = setInterval(function () {
        count--;
        if (num) num.textContent = count;
        if (count <= 0) {
          clearInterval(iv);
          if (action === 'reload') w.location.reload();
        }
      }, 1000);

      el.addEventListener('click', function () {
        clearInterval(iv);
        if (action === 'reload') w.location.reload();
      });
    });
  });

}(window, document));
