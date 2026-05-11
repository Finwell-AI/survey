window.__RECAPTCHA_SITE_KEY__ = '6LcvZ9wsAAAAAAYrl_5cZwa55YM_geBd12_UihAS';
/* Finwell AI — site behaviour
 *
 * Multi-page production version. Each HTML page renders standalone; this script
 * runs the same on every page and uses `document.body.dataset.page` to decide
 * which features to wire up.
 */
(function () {
  'use strict';

  var BODY_PAGE = (document.body && document.body.dataset.page) || 'home';

  // -------------------------------------------------------------- analytics
  // GA4 (`gtag`) is loaded by the page <head>. Behaviour depends on whether
  // Cookiebot is enabled at build time:
  //   - Cookiebot enabled  → events fire to gtag only after the user grants
  //     `statistics` consent; pre-consent events are buffered to dataLayer
  //     with `_denied: true` for inspection.
  //   - Cookiebot disabled → window.Cookiebot is undefined, the consented
  //     check evaluates to undefined-falsy, and we fall through to firing
  //     gtag directly. Same code path; no build-time substitution needed.
  function fwEvent(name, params) {
    try {
      window.dataLayer = window.dataLayer || [];
      var cookiebotPresent = !!(window.Cookiebot && window.Cookiebot.consent);
      // No Cookiebot → treat as "consented" so events flow to gtag.
      // Cookiebot present → require its `statistics` flag.
      var consented = !cookiebotPresent || window.Cookiebot.consent.statistics;
      if (consented && typeof window.gtag === 'function') {
        window.gtag('event', name, params || {});
      } else {
        window.dataLayer.push({ event: name, _denied: !consented, params: params || {} });
      }
    } catch (e) { /* swallow */ }
  }

  // Single global click listener: any element with `data-event` fires that
  // event with all `data-*` attributes (kebab → snake) as parameters.
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-event]');
    if (!el) return;
    var name = el.dataset.event;
    var params = {};
    Object.keys(el.dataset).forEach(function (k) {
      if (k === 'event') return;
      params[k.replace(/[A-Z]/g, function (m) { return '_' + m.toLowerCase(); })] = el.dataset[k];
    });
    fwEvent(name, params);
  });

  // ------------------------------------------------------------- urgent banner
  window.fwDismissBanner = function () {
    var b = document.getElementById('urgentBanner');
    if (b) b.classList.add('hidden');
  };

  // ------------------------------------------------------------- chat FAB
  // Disabled per founder 2026-05-07. Build script (build_pages.py:CHAT_FAB_ENABLED)
  // also strips the markup so the global handlers below are unreachable.
  // Kept commented so re-enable is a single flag flip + uncomment.
  /*
  window.fwToggleChat = function () {
    var panel = document.getElementById('chatPanel');
    var fab = document.getElementById('chatFab');
    if (!panel || !fab) return;
    var open = panel.classList.toggle('open');
    fab.classList.toggle('open', open);
    if (open) {
      fwEvent('chat_opened', {});
      var inp = document.getElementById('chatInput');
      if (inp) inp.focus();
    }
  };

  window.fwAsk = function (q) {
    var inp = document.getElementById('chatInput');
    if (inp) inp.value = q;
    window.fwSendChat({ preventDefault: function () {} });
  };

  function chatAddMsg(text, who) {
    var body = document.getElementById('chatBody');
    if (!body) return;
    var div = document.createElement('div');
    div.className = 'chat-msg ' + who;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  }

  function cannedReply(q) {
    var l = q.toLowerCase();
    if (/(advice|recommend|should i|tell me what|advise)/.test(l)) return "Finwell AI does not give financial, tax or investment advice. We organise your spending and report it back. Decisions stay with you. For advice on your circumstances, please speak to a registered tax agent or licensed financial adviser.";
    if (/(safe|secure|data|protect|privacy|encryp)/.test(l)) return "Yes. Account setup runs through licensed Australian infrastructure. Finwell AI never sees card numbers and never has the ability to move money. We receive transaction data only, encrypted in transit and at rest. AES-256 encryption, Australian hosting. You can disconnect anytime. We will never sell your data.";
    if (/(don.?t pay|don.?t claim|no tax|not.*tax|just.*budget|curious)/.test(l)) return "Plenty of people use Finwell AI just as a budget tool. You get taxable item breakdowns from every purchase, an AI search bar that answers questions about your transaction history, and a clean record across everything you spend. The day your tax position changes, your history is already there.";
    if (/(launch|when|date|live|release|coming)/.test(l)) return "We are scheduled to launch in 2026. Founding members who take the survey get early beta access before then. Take the survey to reserve your place.";
    if (/(cost|price|pricing|how much|paid|tier|plan)/.test(l)) return "We are still validating pricing. The survey asks what feels fair, with three tiers as starting points: $20 Lite, $30 Standard, $40 Full. Founding members who take the survey get six months free at launch.";
    if (/(account|cpa|tax agent|bookkeeper|replace)/.test(l)) return "Finwell AI does not replace your accountant. It makes them faster and cheaper. You hand them a clean, pre-categorised dataset instead of a shoebox. Your accountant gets desktop access to fine-tune categories at the end. They focus on judgement calls, not data entry.";
    if (/(bas|gst|sole trader|abn)/.test(l)) return "Sole traders get BAS data pre-collated. GST identified at the line-item level so your quarterly work is largely prepared before you, or your tax agent, start. Item-level capture means every receipt and tax invoice is stored and searchable.";
    if (/(receipt|photo|scan|upload|paper)/.test(l)) return "You will never take a photo of a receipt again. Finwell AI receives your tax invoice automatically the moment you tap your card. No uploads, no scanning, no shoebox. Every invoice is stored and organised, AI categorised against ATO guidelines.";
    if (/(item|sku|level|how.*track|breakdown)/.test(l)) return "Most bank apps see Coles, $87. Finwell AI sees the milk, the bread, the dog food and the chocolate bar that made up that $87. We capture itemised tax invoices, so your records are real, not guessed.";
    if (/(survey|how long|2 minute|take part)/.test(l)) return "The survey takes 2 minutes, 7 questions. It tells us what to prioritise as we build. In return, you get six months of Premium free at launch if you are in the first 1,000.";
    if (/(financial wellness|stand for|finwell|name|mean)/.test(l)) return "Finwell stands for Financial Wellness. We help you understand, improve and take control of your financial life. Not just at tax time. All year, every year.";
    if (/(hi|hey|hello|g.?day|yo)/.test(l)) return "G'day. Happy to answer anything about Finwell AI. Try asking about how it works, pricing, safety, or when we launch.";
    if (/(point|reward|qantas|frequent flyer|cashback)/.test(l)) return "We are exploring a points or rewards element as part of the platform. The survey asks whether you would value that. Your answer shapes whether we prioritise it.";
    return "Good question. Finwell AI is a fully automated bookkeeper for everyday Australians, dealing with tax, receipts, and financial admin. We capture every receipt, sort every line, and keep your tax position current. We are launching in 2026 and we want input from real users while we build. Take the survey to help shape it.";
  }

  window.fwSendChat = function (e) {
    if (e && e.preventDefault) e.preventDefault();
    var inp = document.getElementById('chatInput');
    if (!inp) return;
    var q = inp.value.trim();
    if (!q) return;
    chatAddMsg(q, 'user');
    inp.value = '';
    setTimeout(function () { chatAddMsg(cannedReply(q), 'bot'); }, 600);
  };
  */
  // ------------------------------------------------------------- end chat FAB (disabled)

  // ------------------------------------------------------------- welcome modal
  // Only fires on the home page; survey/thanks/etc. skip it entirely.
  function setupWelcomeModal() {
    if (BODY_PAGE !== 'home') return;
    var modal = document.getElementById('welcomeModal');
    if (!modal) return;

    var shown = false;
    function show(reason) {
      if (shown) return;
      shown = true;
      modal.classList.add('show');
      document.body.style.overflow = 'hidden';
      fwEvent('modal_opened', { reason: reason });
    }
    window.fwShowWelcome = function () { show('manual'); };

    window.fwCloseWelcome = function () {
      modal.classList.remove('show');
      document.body.style.overflow = '';
      fwEvent('modal_dismissed', {});
      try { sessionStorage.setItem('fw_welcome_dismissed_at', Date.now().toString()); } catch (e) {}
    };

    // Once-per-session: if user already dismissed it, leave them alone.
    try {
      if (sessionStorage.getItem('fw_welcome_dismissed_at')) return;
    } catch (e) {}

    setTimeout(function () { show('timer'); }, 1500);
    if (document.readyState === 'complete') {
      setTimeout(function () { show('already-loaded'); }, 100);
    } else {
      window.addEventListener('load', function () {
        setTimeout(function () { show('window-load'); }, 800);
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('show')) {
        window.fwCloseWelcome();
      }
    });
  }

  // ------------------------------------------------------------- digital receipts animation
  function initDigitalReceipts() {
    var section = document.querySelector('.digital-receipts');
    if (!section) return;
    var items = section.querySelectorAll('.dr-receipt-item');
    var fillBar = section.querySelector('#drConfidenceFill');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        items.forEach(function (item, ix) {
          setTimeout(function () { item.classList.add('in'); }, 200 + ix * 220);
        });
        if (fillBar) {
          setTimeout(function () { fillBar.classList.add('in'); }, 200 + items.length * 220);
        }
        io.unobserve(entry.target);
      });
    }, { threshold: 0.25 });
    io.observe(section);
  }

  function initRevealOnScroll() {
    var els = document.querySelectorAll('.reveal');
    if (!els.length) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) e.target.classList.add('in'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -10% 0px' });
    els.forEach(function (el) { io.observe(el); });
  }

  // ------------------------------------------------------------- nav events
  function wireNavEvents() {
    document.querySelectorAll('.nav-links a').forEach(function (a) {
      if (!a.dataset.event) {
        a.dataset.event = 'nav_click';
        a.dataset.ctaLabel = (a.textContent || '').trim().toLowerCase().replace(/\s+/g, '_');
      }
    });
  }

  // ------------------------------------------------------------- FAQ events
  function wireFaqEvents() {
    document.querySelectorAll('.faq-item, .faq-question, .faq summary, .faq details').forEach(function (el) {
      el.addEventListener('click', function () {
        var label = (el.querySelector('.faq-question, summary, h3') || el).textContent.trim().slice(0, 80);
        fwEvent('faq_opened', { faq_question: label });
      });
    });
  }

  // ------------------------------------------------------------- survey state
  // Only run on the survey page. The pane index (data-step="N") is sequential
  // and may include silent transition panes (data-silent: welcome screen,
  // pricing setup screen). The visible question number comes from data-q-num
  // on each real-question pane (1..12), and drives the progress bar.
  var fwState = { surveyStep: 0, answers: {}, started: false };
  window.fwState = fwState;

  var PRICE_FIELDS = ['price_too_cheap', 'price_bargain', 'price_expensive', 'price_too_expensive'];

  function fwTotalSteps() {
    return document.querySelectorAll('.step-pane').length;
  }

  function fwCurrentPane() {
    return document.querySelector('.step-pane[data-step="' + fwState.surveyStep + '"]');
  }

  function fwGotoStep(n) {
    var total = fwTotalSteps();
    if (total === 0 || n < 0 || n >= total) return;
    document.querySelectorAll('.step-pane').forEach(function (s) { s.classList.remove('on'); });
    var pane = document.querySelector('.step-pane[data-step="' + n + '"]');
    if (!pane) return;
    pane.classList.add('on');
    fwState.surveyStep = n;

    // Progress bar: only show on real-question panes (those with data-q-num).
    var progress = document.getElementById('surveyProgress');
    var qNum = pane.getAttribute('data-q-num');
    if (progress) {
      if (qNum) {
        progress.hidden = false;
        var qNumInt = parseInt(qNum, 10);
        var lbl = document.getElementById('stepLbl');
        if (lbl) lbl.textContent = (qNumInt < 10 ? '0' : '') + qNumInt;
        var dots = progress.querySelectorAll('.ticks span');
        dots.forEach(function (d, i) {
          d.classList.remove('done', 'active');
          if (i + 1 < qNumInt) d.classList.add('done');
          if (i + 1 === qNumInt) d.classList.add('active');
        });
      } else {
        progress.hidden = true;
      }
    }

    // Recompute pane-specific gating on entry (covers Back navigation).
    if (pane.hasAttribute('data-multi-q')) {
      updateMultiStatus(pane.getAttribute('data-multi-q'));
      updateMultiContinue();
    }
    if (pane.querySelector('.price-input')) {
      updatePriceContinue(pane);
    }
    if (pane.querySelector('#submitBtn')) {
      updateSubmitState();
    }

    var card = document.querySelector('.survey-card');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  window.fwNext = function () {
    if (fwState.surveyStep >= fwTotalSteps() - 1) return;
    if (!fwState.started) {
      fwState.started = true;
      fwEvent('survey_started', {});
    }
    fwEvent('survey_step_completed', { step_number: fwState.surveyStep });
    fwGotoStep(fwState.surveyStep + 1);
  };
  window.fwBack = function () {
    if (fwState.surveyStep > 0) fwGotoStep(fwState.surveyStep - 1);
  };
  // Exposed for e2e tests + manual debugging in DevTools. Not part of the
  // public API the survey UI itself needs.
  window.fwGotoStep = fwGotoStep;

  function paneContinueButton(pane) {
    return pane && pane.querySelector('.survey-actions .btn-primary');
  }

  function bindSurveyOptions() {
    // Single-select option buttons — pick one, auto-advance to next pane.
    document.querySelectorAll('.opt:not(.multi)').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var q = btn.dataset.q;
        var v = btn.dataset.v;
        document.querySelectorAll('[data-q="' + q + '"]:not(.multi)').forEach(function (b) { b.classList.remove('selected'); });
        btn.classList.add('selected');
        fwState.answers[q] = v;
        var pane = btn.closest('.step-pane');
        var nb = paneContinueButton(pane);
        if (nb) nb.disabled = false;
        setTimeout(function () { window.fwNext(); }, 420);
      });
    });

    // 1-10 scale buttons — same pattern.
    document.querySelectorAll('.scale-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var q = btn.dataset.q;
        var v = btn.dataset.v;
        document.querySelectorAll('[data-q="' + q + '"]').forEach(function (b) { b.classList.remove('selected'); });
        btn.classList.add('selected');
        fwState.answers[q] = v;
        var pane = btn.closest('.step-pane');
        var nb = paneContinueButton(pane);
        if (nb) nb.disabled = false;
        setTimeout(function () { window.fwNext(); }, 420);
      });
    });

    // Multi-select with optional cap (data-multi-cap on the pane).
    document.querySelectorAll('.opt.multi').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var pane = btn.closest('.step-pane');
        var capAttr = pane && pane.getAttribute('data-multi-cap');
        var cap = capAttr ? parseInt(capAttr, 10) : 0;
        var q = btn.dataset.q;
        var v = btn.dataset.v;
        if (!fwState.answers[q]) fwState.answers[q] = { selected: [] };
        var ans = fwState.answers[q];
        var ix = ans.selected.indexOf(v);
        if (ix >= 0) {
          ans.selected.splice(ix, 1);
          btn.classList.remove('selected');
        } else {
          if (cap && ans.selected.length >= cap) return; // cap reached, ignore
          ans.selected.push(v);
          btn.classList.add('selected');
        }
        refreshMultiCap(pane);
        updateMultiStatus(q);
        updateMultiContinue();
      });
    });

    // Currency inputs for the Van Westendorp price block.
    PRICE_FIELDS.forEach(function (id) {
      var inp = document.getElementById(id);
      if (!inp) return;
      inp.addEventListener('input', function () {
        // Strip non-digits — protects against pasted "$30/mo" content.
        var clean = inp.value.replace(/[^0-9]/g, '');
        if (clean !== inp.value) inp.value = clean;
        fwState.answers[id] = clean;
        var pane = inp.closest('.step-pane');
        updatePriceContinue(pane);
        if (id === 'price_too_expensive') checkVwMonotonic();
      });
      inp.addEventListener('blur', function () {
        if (id === 'price_too_expensive') checkVwMonotonic();
      });
    });

    var emailInp = document.getElementById('email');
    if (emailInp) emailInp.addEventListener('input', updateSubmitState);
    var consentInp = document.getElementById('consent');
    if (consentInp) consentInp.addEventListener('change', updateSubmitState);
  }

  function refreshMultiCap(pane) {
    if (!pane) return;
    var capAttr = pane.getAttribute('data-multi-cap');
    if (!capAttr) return;
    var cap = parseInt(capAttr, 10);
    var q = pane.getAttribute('data-multi-q');
    var ans = fwState.answers[q];
    var atCap = ans && ans.selected.length >= cap;
    pane.querySelectorAll('.opt.multi').forEach(function (b) {
      if (b.classList.contains('selected')) {
        b.classList.remove('disabled');
      } else if (atCap) {
        b.classList.add('disabled');
      } else {
        b.classList.remove('disabled');
      }
    });
  }

  function updateMultiStatus(q) {
    var ans = fwState.answers[q];
    var status = document.getElementById('status_' + q);
    var countEl = document.getElementById('count_' + q);
    if (!status || !countEl) return;
    var pane = document.querySelector('.step-pane[data-multi-q="' + q + '"]');
    var capAttr = pane && pane.getAttribute('data-multi-cap');
    var n = (ans && ans.selected) ? ans.selected.length : 0;
    countEl.textContent = capAttr ? (n + ' of ' + capAttr + ' selected') : (n + ' selected');
    status.classList.toggle('has-top', n > 0);
  }

  function updateMultiContinue() {
    var pane = fwCurrentPane();
    if (!pane || !pane.hasAttribute('data-multi-q')) return;
    var q = pane.getAttribute('data-multi-q');
    var ans = fwState.answers[q];
    var ok = ans && ans.selected.length > 0;
    var nb = paneContinueButton(pane);
    if (nb) nb.disabled = !ok;
  }

  function updatePriceContinue(pane) {
    if (!pane) return;
    var inp = pane.querySelector('.price-input');
    if (!inp) return;
    var v = parseInt(inp.value, 10);
    var ok = !isNaN(v) && v >= 0;
    var nb = paneContinueButton(pane);
    if (nb) nb.disabled = !ok;
  }

  function checkVwMonotonic() {
    var warn = document.getElementById('vwWarning');
    if (!warn) return;
    var p1 = parseInt(fwState.answers['price_too_cheap'], 10);
    var p2 = parseInt(fwState.answers['price_bargain'], 10);
    var p3 = parseInt(fwState.answers['price_expensive'], 10);
    var p4 = parseInt(fwState.answers['price_too_expensive'], 10);
    if (isNaN(p1) || isNaN(p2) || isNaN(p3) || isNaN(p4)) {
      warn.hidden = true;
      return;
    }
    var ok = (p1 <= p2) && (p2 <= p3) && (p3 <= p4);
    warn.hidden = ok;
  }

  function updateSubmitState() {
    var emailEl = document.getElementById('email');
    var consentEl = document.getElementById('consent');
    if (!emailEl || !consentEl) return;
    var email = emailEl.value.trim();
    var ve = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    var consent = consentEl.checked;
    var btn = document.getElementById('submitBtn');
    // Per-pane gating means by the time we land on Q12, all earlier answers
    // are already locked in. Submit only needs email + consent.
    if (btn) btn.disabled = !(ve && consent);
  }

  // Copy in-memory answers into the form's hidden inputs so Netlify captures them.
  // Currency inputs (price_*) are real <input> fields and POST natively, so
  // they don't need syncing from fwState.
  function syncAnswersToForm() {
    var form = document.getElementById('surveyForm');
    if (!form) return;
    var fields = ['segment', 'lost_receipt', 'tax_stress', 'deduction_confidence', 'points_willingness'];
    fields.forEach(function (name) {
      var el = form.elements[name];
      if (el && fwState.answers[name] != null) el.value = fwState.answers[name];
    });
    // Multi-select: comma-separated for HubSpot ingestion.
    ['top_feature', 'trust_builder'].forEach(function (name) {
      var el = form.elements[name];
      var ans = fwState.answers[name];
      if (el && ans && Array.isArray(ans.selected)) el.value = ans.selected.join(',');
    });
  }

  // Inject the reCAPTCHA v3 script once, on first user interaction with the
  // survey form. Saves ~370KB of unused JS on initial paint.
  //
  // Cookiebot consent gating: while Cookiebot is disabled (see build_pages.py
  // COOKIEBOT_ENABLED flag), reCAPTCHA loads on first interaction without
  // waiting for any consent. When Cookiebot is re-enabled, the check below
  // automatically defers loading until the user accepts the `security`
  // cookie category. No code change required at re-enable time other than
  // flipping the build flag.
  var _recaptchaLoaded = false;
  function loadRecaptchaIfNeeded() {
    if (_recaptchaLoaded) return;
    if (!window.__RECAPTCHA_LAZY__) return; // not on this page
    var key = window.__RECAPTCHA_SITE_KEY__ || '';
    if (!key || key.indexOf('MISSING_') === 0) return;
    if (window.Cookiebot && window.Cookiebot.consent && !window.Cookiebot.consent.security) {
      // Cookiebot is active and security consent not granted yet — defer
      // until user accepts. This event fires once consent is updated. With
      // Cookiebot disabled, window.Cookiebot is undefined and this branch
      // is skipped, so reCAPTCHA loads on first interaction.
      window.addEventListener('CookiebotOnAccept', loadRecaptchaIfNeeded);
      return;
    }
    _recaptchaLoaded = true;
    var s = document.createElement('script');
    s.src = 'https://www.google.com/recaptcha/api.js?render=' + encodeURIComponent(key);
    s.async = true;
    s.defer = true;
    document.head.appendChild(s);
  }

  // Get reCAPTCHA v3 token and write it into the hidden form field.
  // Robust to: missing site key, deploy-time MISSING_* placeholders, grecaptcha
  // not loaded, sync exceptions from grecaptcha.execute, and stuck promises —
  // never blocks the form for longer than 3s.
  function getRecaptchaToken() {
    return new Promise(function (resolve) {
      var done = false;
      function once(v) { if (done) return; done = true; resolve(v); }
      // Hard ceiling: don't let a broken reCAPTCHA hang the form forever.
      setTimeout(function () { once(''); }, 3000);

      var siteKey = window.__RECAPTCHA_SITE_KEY__ || '';
      // Treat the build-time fallback string as no key.
      if (!siteKey || siteKey.indexOf('MISSING_') === 0
          || !window.grecaptcha || !window.grecaptcha.execute) {
        return once('');
      }
      try {
        window.grecaptcha.ready(function () {
          try {
            window.grecaptcha.execute(siteKey, { action: 'submit' }).then(
              function (token) { once(token); },
              function () { once(''); }
            );
          } catch (inner) { once(''); }
        });
      } catch (outer) { once(''); }
    });
  }

  function setupSurveyForm() {
    if (BODY_PAGE !== 'survey') return;
    bindSurveyOptions();
    var form = document.getElementById('surveyForm');
    if (!form) return;

    // Trigger reCAPTCHA load on first interaction so the 370KB script isn't
    // on the critical render path. By the time the user reaches step 8 and
    // clicks Submit, grecaptcha has had plenty of time to download. We use
    // the bubble phase (no capture) so the option-button click handlers fire
    // first and the step transition isn't held up by the script append.
    var loadOnce = function () { loadRecaptchaIfNeeded(); };
    form.addEventListener('click', loadOnce, { once: true, passive: true });
    form.addEventListener('focusin', loadOnce, { once: true, passive: true });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      // Final validation gate
      updateSubmitState();
      var btn = document.getElementById('submitBtn');
      if (btn && btn.disabled) return;

      btn.disabled = true;
      btn.textContent = 'Submitting…';

      syncAnswersToForm();

      getRecaptchaToken().then(function (token) {
        var tokField = document.getElementById('recaptchaToken');
        if (tokField) tokField.value = token;

        // If we have a token AND a verify endpoint, check it server-side first.
        var p = token
          ? fetch('/.netlify/functions/verify-recaptcha', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ token: token })
            }).then(function (r) { return r.ok; })
          : Promise.resolve(true);

        p.then(function (ok) {
          if (!ok) {
            btn.disabled = false;
            btn.textContent = 'Submit';
            alert('Spam check failed. Please refresh and try again.');
            return;
          }
          fwEvent('survey_completed', {});
          // Now submit natively so Netlify Forms captures the POST.
          form.submit();
        });
      });
    });
  }

  // ------------------------------------------------------------- service worker
  // Register on idle so it doesn't fight the LCP path. The SW caches
  // /assets/* and serves repeat visits from cache.
  function registerSW() {
    if (!('serviceWorker' in navigator)) return;
    if (location.protocol !== 'https:' && location.hostname !== 'localhost') return;
    try { navigator.serviceWorker.register('/sw.js'); } catch (e) { /* swallow */ }
  }

  // ------------------------------------------------------------- boot
  document.addEventListener('DOMContentLoaded', function () {
    setupWelcomeModal();
    initDigitalReceipts();
    initRevealOnScroll();
    wireNavEvents();
    wireFaqEvents();
    setupSurveyForm();
    var idleSW = function () { registerSW(); };
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(idleSW, { timeout: 4000 });
    } else {
      setTimeout(idleSW, 1500);
    }
  });
})();
