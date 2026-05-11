(function($){
  function reindex(){
    $('#tvln-reviews-list .tvln-review-row').each(function(i){
      $(this).attr('data-index', i);
      $(this).find('.tvln-review-row__header strong').text('Review #' + (i+1));
      $(this).find('input, select, textarea').each(function(){
        var name = $(this).attr('name'); if(!name) return;
        name = name.replace(/reviews\[\d+\]/, 'reviews['+i+']');
        $(this).attr('name', name);
      });
    });
  }
  $(document).ready(function(){
    $('.tvln-color').wpColorPicker();
    $('#tvln-add-review').on('click', function(){
      var idx = $('#tvln-reviews-list .tvln-review-row').length;
      var tpl = $('#tvln-review-row-template').html()
        .replaceAll('{{INDEX}}', idx)
        .replaceAll('{{NUM}}', idx+1);
      $('#tvln-reviews-list').append(tpl);
      reindex();
    });
    $('#tvln-reviews-list').on('click', '.tvln-remove-review', function(e){
      e.preventDefault();
      $(this).closest('.tvln-review-row').remove();
      reindex();
    });
  });
})(jQuery);
