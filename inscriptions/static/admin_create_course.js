$(function() {
    COURSE_MODEL = {};
    $.ajax('/static/course_models.json', {
        success: function(r) {
            COURSE_MODEL = r;
        }
    });
    var $place = $('<div>');
    $('fieldset')
        .append($('<div class="form-row">')
            .append($('<label class="required">').html('Tarifs&nbsp;:'))
            .append($place)
        );

    $('[name=course_model]').click(function() {
        var model = COURSE_MODEL[this.value];

        var $table = $('<table>')
            .append($('<tr>')
                .append($('<th>').html('Code'))
                .append($('<td>').html('Nom'))
                .append($('<td>').html('Prix standard'))
                .append($('<td>').html('Prix augmenté'))
            );
        $place.html($table);
        model.categories.forEach(function(c) {
            $('<tr>')
                .append($('<th>').html(c.code))
                .append($('<td>').html(c.nom))
                .append($('<td>').append($('<input>').attr('name', c.code + '_prix1').val(c.prix1)))    
                .append($('<td>').append($('<input>').attr('name', c.code + '_prix2').val(c.prix2)))    
                .appendTo($table);
        });
        $table.find('input').change(function() {
            d = {};
            $table.find('input').each(function() {
                n = this.name.split('_');
                d[n[0]] = d[n[0]] || {}
                d[n[0]][n[1]]= parseFloat(this.value) || 0;
            });
            $('[name=course_prix]').val(JSON.stringify(d));
        });
    });
});
