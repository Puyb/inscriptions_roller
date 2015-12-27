$(function() {
    COURSE_MODEL = {};
    $.ajax('/static/course_models.json', {
        success: function(r) {
            COURSE_MODEL = r;
            generate_prices($('[name=course_model]:checked').val());
        }
    });
    var $place = $('<div>');
    $('fieldset')
        .append($('<div class="form-row">')
            .append($('<label class="required">').html('Tarifs&nbsp;:'))
            .append($place)
        );

    function generate_prices(model_name) {
        if (!model_name) return;
        var model = COURSE_MODEL[model_name];

        var $table = $('<table>')
            .append($('<tr>')
                .append($('<th>').html('Code'))
                .append($('<td>').html('Nom'))
                .append($('<td>').html('Prix standard'))
                .append($('<td>').html('Prix augmenté'))
            );
        previous = JSON.parse($('[name=course_prix]').val() || '{}');
        $place.html($table);
        model.categories.forEach(function(c) {
            $('<tr>')
                .append($('<th>').html(c.code))
                .append($('<td>').html(c.nom))
                .append($('<td>').append($('<input>').attr('name', c.code + '_prix1').val(c.code in previous ? previous[c.code].prix1 : c.prix1)))    
                .append($('<td>').append($('<input>').attr('name', c.code + '_prix2').val(c.code in previous ? previous[c.code].prix2 : c.prix2)))    
                .appendTo($table);
        });
        $table.find('input').change(updateField);
        function updateField() {
            d = {};
            $table.find('input').each(function() {
                n = this.name.split('_');
                d[n[0]] = d[n[0]] || {}
                d[n[0]][n[1]]= parseFloat(this.value) || 0;
            });
            $('[name=course_prix]').val(JSON.stringify(d));
        }
        updateField();
    }
    $('[name=course_model]').click(function() {
        generate_prices(this.value);
    });
});
