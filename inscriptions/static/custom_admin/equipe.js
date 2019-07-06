$(function() {
    if(!$('#equipe_form').length) return;

    $('.field-piece_jointe .field-piece_jointe div.readonly, .field-piece_jointe .field-autorisation div.readonly').each(function() {
        if(this.textContent == '')
            this.innerHTML = 'Aucun fichier joint';
        else
            this.innerHTML = '<a href="/uploads/' + this.textContent + '" target="_blank">' + this.textContent + '</a>';
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


