$(function() {
    if(!$('#equipe_form').length) return;

    $('.fieldBox.field-piece_jointe div.readonly, .fieldBox.field-autorisation div.readonly').each(function() {
        // Django >= 3.x affiche "-" (empty_value_display) pour un fichier vide
        var text = $.trim(this.textContent);
        if(text == '' || text == '-')
            this.innerHTML = 'Aucun fichier joint';
        else
            this.innerHTML = '<a href="/uploads/' + text + '" target="_blank">' + text + '</a>';
    });

    $('.field-age>div.readonly').each(function() {
        if(parseFloat(this.textContent) >= 18) {
            $(this).parents('.form-row').next().hide();
        }
    
    });
    $('#equipier_set-group .help').remove();

    $.get('../autre/', function(data) {
        $('#autre').html(data);
    });
});


