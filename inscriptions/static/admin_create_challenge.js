$(function() {
    COURSE_MODEL = {};
    $.ajax('/static/course_models.json', {
        success: function(r) {
            COURSE_MODEL = r;
            generate_cat($('[name=course_model]:checked').val());
        }
    });
    var $place = $('<div>');
    $('fieldset:first-child')
        .append($('<div class="form-row">')
            .append($('<label class="required">').html('Catégories&nbsp;:'))
            .append($place)
        );

    function generate_cat(model_name) {
        if (!model_name) return;
        var model = COURSE_MODEL[model_name];

        var $table = $('<table>')
            .append($('<tr>')
                .append($('<th>').html('Code'))
                .append($('<td>').html('Nom'))
            );
        $place.empty().append($table);
        if(model.categories)
            model.categories.forEach(function(c) {
                $('<tr>')
                    .append($('<th>').html(c.code))
                    .append($('<td>').html(c.nom))
                    .appendTo($table);
            });
    }
    $('[name=course_model]').click(function() {
        generate_cat(this.value);
    });
});
