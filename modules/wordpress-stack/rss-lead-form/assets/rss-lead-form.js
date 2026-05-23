/**
 * RSS Lead Form — client-side logic.
 *
 * Multi-step form navigation, validation, AJAX submission, and keyboard shortcuts.
 * Requires window.RSS_LF_CONFIG to be set by the shortcode output:
 *   { ajaxUrl, nonce, successPagePath, phoneForErrors }
 */
(function() {
"use strict";

var root = document.querySelector('.rss-lf-root');
if (!root) return;

// ============ STATE ============
var path = null;
var formHistory = ['intro'];
var pathSteps = {
  buyer: 3,
  seller: 4,
  va: 3,
  market: 2,
  neighborhood: 2,
  other: 2
};

// ============ NAVIGATION ============
function getProgress(screenId) {
  if (screenId === 'intro') return 0;
  if (screenId === 'confirmation') return 100;
  if (!path) return 0;
  var total = pathSteps[path] || 3;
  var current = 1;
  if (screenId.includes('-2')) current = 2;
  else if (screenId.includes('-3')) current = 3;
  else if (screenId === 'contact') current = total;
  return Math.round((current / total) * 100);
}

function go(screenId) {
  var current = root.querySelector('.screen.active');
  var next = root.querySelector('.screen[data-screen="' + screenId + '"]');
  if (!next || current === next) return;

  if (current) current.classList.remove('active');

  setTimeout(function() {
    next.classList.add('active');
    var fill = root.querySelector('#progress-fill');
    if (fill) fill.style.width = getProgress(screenId) + '%';

    if (screenId === 'contact') {
      var submitBtn = root.querySelector('#contact-submit-btn');
      if (submitBtn) {
        var submitLabels = {
          buyer: 'Connect me with a buyer agent →',
          seller: 'Get my free home valuation →',
          va: 'Connect me with a VA specialist →',
          neighborhood: 'Start sending alerts →',
          other: 'Send my message →'
        };
        submitBtn.innerHTML = submitLabels[path] || 'Send my request →';
      }
    }

    var input = next.querySelector('.input, .textarea');
    if (input) setTimeout(function() { input.focus(); }, 200);
  }, current ? 280 : 0);
}

function goNext(screenId) {
  formHistory.push(screenId);
  go(screenId);
}

function goBack() {
  if (formHistory.length <= 1) return;
  formHistory.pop();
  go(formHistory[formHistory.length - 1]);
}

// ============ PATH PICKER ============
root.querySelectorAll('.path').forEach(function(btn) {
  btn.addEventListener('click', function() {
    path = btn.dataset.path;
    var firstScreen = path === 'buyer' ? 'buyer-1'
      : path === 'seller' ? 'seller-1'
      : path === 'va' ? 'va-1'
      : path === 'market' ? 'market-1'
      : path === 'neighborhood' ? 'hood-1'
      : 'other-1';
    goNext(firstScreen);
  });
});

// ============ AUTO-ADVANCE ANSWERS ============
root.querySelectorAll('.ans[data-auto]').forEach(function(btn) {
  btn.addEventListener('click', function() {
    btn.parentElement.querySelectorAll('.ans').forEach(function(a) {
      a.classList.remove('selected');
    });
    btn.classList.add('selected');
    setTimeout(function() { goNext(btn.dataset.next); }, 220);
  });
});

// ============ MULTI-SELECT CHIPS ============
root.querySelectorAll('.chips').forEach(function(group) {
  group.addEventListener('click', function(e) {
    var chip = e.target.closest('.chip');
    if (!chip) return;
    chip.classList.toggle('selected');
    var screen = group.closest('.screen');
    var continueBtn = screen.querySelector('[data-next], [data-submit]');
    if (continueBtn) {
      continueBtn.disabled = group.querySelectorAll('.chip.selected').length === 0;
    }
  });
});

// ============ TEXT INPUT VALIDATION ============
root.querySelectorAll('.input, .textarea').forEach(function(input) {
  input.addEventListener('input', function() {
    var screen = input.closest('.screen');
    var btn = screen.querySelector('[data-require]');
    var btnAll = screen.querySelector('[data-require-all]');

    if (btn) {
      var field = screen.querySelector('[name="' + btn.dataset.require + '"]');
      if (field) btn.disabled = !field.value.trim();
    }
    if (btnAll) {
      var fields = btnAll.dataset.requireAll.split(',');
      btnAll.disabled = !fields.every(function(name) {
        var f = screen.querySelector('[name="' + name + '"]');
        return f && f.value.trim();
      });
    }
  });

  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && input.tagName !== 'TEXTAREA') {
      e.preventDefault();
      var screen = input.closest('.screen');
      var btn = screen.querySelector('[data-next]:not(:disabled), [data-submit]:not(:disabled)');
      if (btn) btn.click();
    }
  });
});

// ============ NEXT BUTTON HANDLERS ============
root.addEventListener('click', function(e) {
  var next = e.target.closest('[data-next]');
  if (next && !next.disabled) goNext(next.dataset.next);
});

// ============ BACK BUTTONS ============
root.addEventListener('click', function(e) {
  if (e.target.closest('[data-back]')) goBack();
});

// ============ COLLECT FORM DATA ============
function collectFormData() {
  var data = {
    path: path || 'unknown',
    firstname: '',
    lastname: '',
    email: '',
    phone: '',
    answers: {},
    referrer: document.referrer || '',
    ref_param: '',
    timestamp: new Date().toISOString(),
    honeypot: ''
  };

  // Parse ?ref= from URL
  var params = new URLSearchParams(window.location.search);
  data.ref_param = params.get('ref') || '';

  // Contact fields
  var fn = root.querySelector('[name="firstname"]');
  var ln = root.querySelector('[name="lastname"]');
  var em = root.querySelector('[name="email"]');
  var ph = root.querySelector('[name="phone"]');
  if (fn) data.firstname = fn.value.trim();
  if (ln) data.lastname = ln.value.trim();
  if (em) data.email = em.value.trim();
  if (ph) data.phone = ph.value.trim();

  // Honeypot
  var hp = root.querySelector('[name="website"]');
  if (hp) data.honeypot = hp.value;

  // Path-specific answers
  if (path === 'buyer') {
    var timeline = root.querySelector('.screen[data-screen="buyer-1"] .ans.selected');
    if (timeline) data.answers['Timeline'] = timeline.dataset.value;
    var areas = root.querySelectorAll('.screen[data-screen="buyer-2"] .chip.selected');
    if (areas.length) data.answers['Area'] = Array.from(areas).map(function(c) { return c.dataset.value; }).join(', ');
  }
  else if (path === 'seller') {
    var addr = root.querySelector('[name="seller-address"]');
    if (addr) data.answers['Property address'] = addr.value.trim();
    var timing = root.querySelector('.screen[data-screen="seller-2"] .ans.selected');
    if (timing) data.answers['Timing'] = timing.dataset.value;
    var buying = root.querySelector('.screen[data-screen="seller-3"] .ans.selected');
    if (buying) data.answers['Buying too?'] = buying.dataset.value;
  }
  else if (path === 'va') {
    var status = root.querySelector('.screen[data-screen="va-1"] .ans.selected');
    if (status) data.answers['Status'] = status.dataset.value;
    var need = root.querySelector('.screen[data-screen="va-2"] .ans.selected');
    if (need) data.answers['Need'] = need.dataset.value;
  }
  else if (path === 'market') {
    var mEmail = root.querySelector('[name="market-email"]');
    if (mEmail) data.answers['Email'] = mEmail.value.trim();
    // Use market email as primary if contact fields empty
    if (!data.email && mEmail) data.email = mEmail.value.trim();
    var zip = root.querySelector('[name="market-zip"]');
    if (zip) data.answers['Area'] = zip.value.trim();
  }
  else if (path === 'neighborhood') {
    var hoods = root.querySelectorAll('.screen[data-screen="hood-1"] .chip.selected');
    if (hoods.length) data.answers['Areas'] = Array.from(hoods).map(function(c) { return c.dataset.value; }).join(', ');
  }
  else if (path === 'other') {
    var msg = root.querySelector('[name="other-message"]');
    if (msg) data.answers['Question'] = msg.value.trim();
  }

  return data;
}

// ============ SUBMIT HANDLER ============
var confirmMessages = {
  buyer: {
    title: 'Talk soon, <em>future homeowner.</em>',
    msg: 'A buyer specialist personally reviews your info and reaches out within one business day.',
    next: 'Personal email or call from an LRG buyer specialist within one business day.'
  },
  seller: {
    title: 'Your valuation is <em>on the way.</em>',
    msg: 'Free professional valuation in your inbox within 24 hours, plus a 2026 selling strategy for your area.',
    next: 'Free professional valuation within 24 hours. No high-pressure follow-up.'
  },
  va: {
    title: 'Thank you for <em>your service.</em>',
    msg: 'A VA-experienced LRG agent will reach out within one business day. PCS requests get priority.',
    next: 'A Veteran-experienced agent will personally call or email within one business day.'
  },
  market: {
    title: 'You\'re <em>signed up.</em>',
    msg: 'First market report lands in your inbox within 24 hours. Monthly after that.',
    next: 'First report in 24 hours. Unsubscribe or adjust areas anytime.'
  },
  neighborhood: {
    title: 'Alerts <em>activated.</em>',
    msg: 'First batch of listings and market signals arrives within 24 hours. Weekly after that.',
    next: 'First neighborhood alert within 24 hours. Pause or change anytime.'
  },
  other: {
    title: 'Got your <em>question.</em>',
    msg: 'Routed to the right specialist on our team. We\'ll respond within one business day.',
    next: 'Specialist response within one business day.'
  }
};

function showError(message) {
  var errEl = root.querySelector('.rss-lf-error');
  if (errEl) {
    errEl.textContent = message;
    errEl.classList.add('visible');
  }
}

function hideError() {
  var errEl = root.querySelector('.rss-lf-error');
  if (errEl) errEl.classList.remove('visible');
}

function showConfirmation(which) {
  var config = confirmMessages[which] || confirmMessages.other;
  var titleEl = root.querySelector('#confirm-title');
  var msgEl = root.querySelector('#confirm-msg');
  var nextEl = root.querySelector('#confirm-next');
  if (titleEl) titleEl.innerHTML = config.title;
  if (msgEl) msgEl.textContent = config.msg;
  if (nextEl) nextEl.textContent = config.next;
  goNext('confirmation');
}

root.addEventListener('click', function(e) {
  var submit = e.target.closest('[data-submit]');
  if (!submit || submit.disabled) return;

  hideError();
  var formData = collectFormData();
  var which = submit.dataset.submit === 'primary' ? path : submit.dataset.submit;

  // Check if we have AJAX config
  var cfg = window.RSS_LF_CONFIG;
  if (!cfg || !cfg.ajaxUrl) {
    // No backend — just show confirmation (fallback for preview)
    showConfirmation(which);
    return;
  }

  // Disable button during submission
  submit.disabled = true;
  var originalText = submit.innerHTML;
  submit.innerHTML = 'Sending...';

  var xhr = new XMLHttpRequest();
  xhr.open('POST', cfg.ajaxUrl);
  xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');

  xhr.onload = function() {
    if (xhr.status === 200) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success) {
          showConfirmation(which);
          return;
        }
      } catch(ex) { /* fall through to error */ }
    }
    // Error path
    submit.disabled = false;
    submit.innerHTML = originalText;
    var phone = cfg.phoneForErrors || '';
    var errMsg = 'Something went wrong submitting your info. Please try again';
    if (phone) errMsg += ' or call us at ' + phone;
    errMsg += '.';
    showError(errMsg);
  };

  xhr.onerror = function() {
    submit.disabled = false;
    submit.innerHTML = originalText;
    showError('Network error. Please check your connection and try again.');
  };

  var params = 'action=rss_lead_form_submit'
    + '&_ajax_nonce=' + encodeURIComponent(cfg.nonce)
    + '&payload=' + encodeURIComponent(JSON.stringify(formData));

  xhr.send(params);
});

// ============ NOTE TOGGLE ============
var noteToggle = root.querySelector('#note-toggle');
var noteEl = root.querySelector('#note');
if (noteToggle && noteEl) {
  noteToggle.addEventListener('click', function() {
    noteEl.classList.toggle('expanded');
  });
}

// ============ KEYBOARD SHORTCUTS ============
document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  var screen = root.querySelector('.screen.active');
  if (!screen) return;
  var key = e.key.toUpperCase();
  if (['A','B','C','D','E','F'].includes(key)) {
    var answers = screen.querySelectorAll('.ans[data-auto]');
    var idx = key.charCodeAt(0) - 65;
    if (answers[idx]) answers[idx].click();
  }
});

})();
