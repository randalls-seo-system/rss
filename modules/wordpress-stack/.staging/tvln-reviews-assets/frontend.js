/* TVLN Reviews v3.5.0 – slider + compact (no clamp) + optional modal + ticker */
(function(){
  function initSlider(root){
    const slider = root.querySelector('.tvln-slider');
    const viewport = root.querySelector('.tvln-viewport');
    const track = root.querySelector('.tvln-track');
    const cards = Array.from(track.children);
    if (!slider || !track || cards.length === 0) return;

    const CLONE = Math.min(4, cards.length);
    const totalOriginals = cards.length;
    for (let i=0;i<CLONE;i++){ track.appendChild(cards[i].cloneNode(true)); }
    for (let i=totalOriginals-CLONE; i<totalOriginals; i++){
      const c = cards[i].cloneNode(true);
      track.insertBefore(c, track.firstChild);
    }

    const getPerView = () => Math.max(1, Math.round(parseFloat(getComputedStyle(root).getPropertyValue('--cards-per-view')) || 1));
    let perView = getPerView();
    let index = CLONE;
    let step = viewport.clientWidth / perView;

    const setTransition = on => { track.style.transition = on ? 'transform 820ms cubic-bezier(.22,.61,.36,1)' : 'none'; };
    const goTo = (i, animate=true) => { if(!animate) setTransition(false); track.style.transform = 'translateX(' + (-i*step) + 'px)'; if(!animate){ track.getBoundingClientRect(); setTransition(true);} };

    goTo(index, false);

    const next = () => { index += 1; goTo(index, true); };
    const prev = () => { index -= 1; goTo(index, true); };

    track.addEventListener('transitionend', () => {
      if (index >= totalOriginals + CLONE) { index -= totalOriginals; goTo(index, false); }
      else if (index < CLONE) { index += totalOriginals; goTo(index, false); }
    });

    const interval = parseInt(root.getAttribute('data-interval'), 10) || 10000;
    const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let timer = null;
    const start = () => { if (prefersReduced) return; if (!timer) timer = setInterval(next, interval); };
    const stop = () => { if (timer) { clearInterval(timer); timer = null; } };
    const reset = () => { stop(); start(); };

    slider.querySelector('.tvln-prev')?.addEventListener('click', (e)=>{ e.preventDefault(); prev(); reset(); });
    slider.querySelector('.tvln-next')?.addEventListener('click', (e)=>{ e.preventDefault(); next(); reset(); });

    slider.addEventListener('mouseenter', stop);
    slider.addEventListener('mouseleave', start);
    slider.addEventListener('focusin', stop);
    slider.addEventListener('focusout', start);

    if ('IntersectionObserver' in window){
      const io = new IntersectionObserver((es)=> es.forEach(e => e.isIntersecting ? start() : stop()), { threshold: 0.25 });
      io.observe(root);
    } else { start(); }

    const recalc = () => { perView = getPerView(); step = viewport.clientWidth / perView; goTo(index, false); };
    window.addEventListener('resize', recalc);
    window.addEventListener('orientationchange', recalc);
    window.addEventListener('load', recalc);

    // Compact behavior
    if (root.classList.contains('tvln-compact')) {
      const behavior = root.getAttribute('data-more') || 'modal';
      const lines = parseInt(getComputedStyle(root).getPropertyValue('--tvln-lines'), 10) || 6;

      // Measure collapsed height by line-height * lines
      root.querySelectorAll('.tvln-card-inner .tvln-body').forEach(body => {
        const lh = parseFloat(getComputedStyle(body).lineHeight) || 20;
        const collapsed = Math.round(lh * lines + 6); // small buffer
        body.style.setProperty('--tvln-collapsed-h', collapsed + 'px');
      });

      // If behavior is modal, prepare modal
      let modal, modalTitle, modalMeta, modalStars, modalBody, modalClose;
      if (behavior === 'modal') {
        // Create once
        modal = document.querySelector('.tvln-modal');
        if (!modal) {
          modal = document.createElement('div');
          modal.className = 'tvln-modal'; modal.setAttribute('aria-hidden','true'); modal.setAttribute('role','dialog');
          modal.innerHTML = '<div class="tvln-modal__panel" role="document"><div class="tvln-modal__head"><h3 class="tvln-modal__title"></h3><button class="tvln-modal__close" type="button">Close</button></div><div class="tvln-modal__meta"></div><div class="tvln-stars"></div><div class="tvln-modal__body"></div></div>';
          document.body.appendChild(modal);
        }
        modalTitle = modal.querySelector('.tvln-modal__title');
        modalMeta  = modal.querySelector('.tvln-modal__meta');
        modalStars = modal.querySelector('.tvln-stars');
        modalBody  = modal.querySelector('.tvln-modal__body');
        modalClose = modal.querySelector('.tvln-modal__close');

        function closeModal(){
          modal.setAttribute('aria-hidden','true');
          document.body.style.overflow = '';
        }
        modalClose.addEventListener('click', closeModal);
        modal.addEventListener('click', (e)=>{ if (e.target === modal) closeModal(); });
        document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') closeModal(); });
      }

      slider.addEventListener('click', function(e){
        const btn = e.target.closest('.tvln-more');
        if (!btn) return;
        const card = btn.closest('.tvln-card-inner');
        const body = card ? card.querySelector('.tvln-body') : null;
        if (!card || !body) return;
        e.preventDefault();

        if (behavior === 'modal') {
          // Fill modal
          const name = card.querySelector('.tvln-name')?.textContent || 'Review';
          const meta = card.querySelector('.tvln-meta')?.textContent || '';
          const rating = card.querySelectorAll('.tvln-card-top .star').length;
          modalTitle.textContent = name;
          modalMeta.textContent = meta;
          // Stars
          modalStars.innerHTML = '';
          for (let i=0;i<rating;i++){
            const s = document.createElementNS('http://www.w3.org/2000/svg','svg');
            s.setAttribute('viewBox','0 0 24 24'); s.classList.add('star');
            s.innerHTML = '<path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/>';
            modalStars.appendChild(s);
          }
          // Body
          modalBody.innerHTML = body.innerHTML;
          document.body.style.overflow = 'hidden';
          modal.setAttribute('aria-hidden','false');
          return;
        }

        // Expand in card (one-open-only)
        const willExpand = !card.classList.contains('is-expanded');
        // collapse others
        slider.querySelectorAll('.tvln-card-inner.is-expanded').forEach(other => {
          if (other === card) return;
          other.classList.remove('is-expanded');
          const obtn = other.querySelector('.tvln-more');
          if (obtn){ obtn.setAttribute('aria-expanded','false'); obtn.textContent='Read more'; }
        });
        // toggle
        card.classList.toggle('is-expanded', willExpand);
        btn.setAttribute('aria-expanded', willExpand ? 'true' : 'false');
        btn.textContent = willExpand ? 'Show less' : 'Read more';
      }, true);
    }
  }

  function initTicker(root){
    const viewport = root.querySelector('.tvln-ticker-viewport');
    const track = root.querySelector('.tvln-ticker-track');
    const items = Array.from(track.children);
    if (!viewport || !track || items.length === 0) return;

    const first = items[0].cloneNode(true);
    const last = items[items.length-1].cloneNode(true);
    track.appendChild(first);
    track.insertBefore(last, track.firstChild);

    let index = 1;
    const setTransition = on => { track.style.transition = on ? 'transform 500ms ease' : 'none'; };
    const width = () => viewport.clientWidth;
    const goTo = (i, animate=true) => { if(!animate) setTransition(false); track.style.transform = 'translateX(' + (-i * width()) + 'px)'; if(!animate){ track.getBoundingClientRect(); setTransition(true);} };
    goTo(index, false);

    track.addEventListener('transitionend', () => {
      const total = items.length;
      if (index >= total + 1) { index = 1; goTo(index, false); }
      else if (index <= 0) { index = total; goTo(index, false); }
    });

    const interval = parseInt(root.getAttribute('data-interval'), 10) || 8000;
    const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let timer = null;
    const start = () => { if (prefersReduced) return; if (!timer) timer = setInterval(()=>{ index += 1; goTo(index, true); }, interval); };
    const stop = () => { if (timer) { clearInterval(timer); timer = null; } };

    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);
    if ('IntersectionObserver' in window){
      const io = new IntersectionObserver((es)=> es.forEach(e => e.isIntersecting ? start() : stop()), { threshold: 0.1 });
      io.observe(root);
    } else { start(); }

    const recalc = () => goTo(index, false);
    window.addEventListener('resize', recalc);
    window.addEventListener('orientationchange', recalc);
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.tvln-module').forEach(initSlider);
    document.querySelectorAll('.tvln-ticker').forEach(initTicker);
  });
})();
