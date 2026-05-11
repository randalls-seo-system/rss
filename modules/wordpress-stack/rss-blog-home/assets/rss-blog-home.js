/* RSS Blog Home v1.0.0 — scroll fade-in */
(function(){
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.rbh-fade').forEach(function(el){ el.classList.add('rbh-visible'); });
    return;
  }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (e.isIntersecting) { e.target.classList.add('rbh-visible'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.rbh-fade').forEach(function(el){ io.observe(el); });
})();
