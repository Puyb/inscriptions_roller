$(function() {
    COURSE_MODEL = {};
    $.ajax('../models/', {
        dataType: 'json',
        success: function(r) {
            COURSE_MODEL = r;
            const field = $('#id_course_model');
            let i = 0;
            for (const [k, v] of Object.entries(r)) {
                field.append($('<li>')
                    .append($('<label>').attr({ for: `id_course_model_${i}` })
                        .append($('<input>').attr({
                            type: 'radio',
                            name: 'course_model',
                            value: k,
                            id: `id_course_model_${i++}`
                        })).append($('<span>').text(' ' + v._name))
                    )
                );
            }
            $('[name=course_model]').click(function() {
                generate_prices(this.value);
            });
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

        const datesAugmentations = $('[name=dates_augmentation]').val().split(',').filter(i => i);
        const tr = $('<tr>')
            .append($('<th>').html('Code'))
            .append($('<td>').html('Nom'))
            .append($('<td>').html('À partir du ' + new Date($('[name=date_ouverture]').val()).toLocaleDateString()))
        for (const d of datesAugmentations) {
            tr.append($('<td>').html('À partir du ' + new Date(d).toLocaleDateString()))
        }
        var $table = $('<table>').append(tr);

        previous = JSON.parse($('[name=course_prix]').val() || '{}');
        $place.html($table);
        if(model.categories)
            model.categories.forEach(function(c) {
                let lastPrice = c.code in previous ? previous[c.code].prices[0] : c.prices[0];
                const tr = $('<tr>')
                    .append($('<th>').html(c.code))
                    .append($('<td>').html(c.nom))
                    .append($('<td>').append($('<input>').attr('name', c.code + '_prix0').val(lastPrice)));
                for (let i = 1; i <= datesAugmentations.length; i++) {
                    tr.append($('<td>').append($('<input>').attr('name', c.code + '_prix' + i).val(lastPrice = ((c.code in previous ? previous[c.code].prices[i] : c.prices[i]) || lastPrice))));
                }
                tr.appendTo($table);
            });
        $table.find('input').change(updateField);
        function updateField() {
            d = {};
            $table.find('input').each(function() {
                n = this.name.split('_prix');
                const cat = d[n[0]] = d[n[0]] || { prices: [] }
                const last = cat.prices[cat.prices.length - 1];
                cat.prices.push(parseFloat(this.value) || last || 0);
            });
            $('[name=course_prix]').val(JSON.stringify(d));
        }
        updateField();
    }
    $(document).ready(function() {
        $('input[name=dates_augmentation]').each(function() {
            const input = $(this);
            input.attr('hidden', true);
            input.before('<table id="dates_augmentation_table"></table><a href="#">Ajouter une date d\'augmentation</a>')
            const values = input.val().split(',');
            function update() {
                const res = [];
                $('#dates_augmentation_table input').each(function() {
                    let v = $(this).val();
                    if (/^\d{2}\/\d{2}\/\d{4}$/.test(v)) v = v.split('/').reverse().join('-');
                    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) res.push(v);
                });
                res.sort();
                input.val(res.join(','));
                generate_prices($('[name=course_model]:checked').val());
            }
            function addDate(d = '') {
                $('#dates_augmentation_table').append('<tr><td><input value="' + d + '"></td><td><button type="button">X</button></td></tr>')
                $('#dates_augmentation_table tr:last input').each(function() {
                    DateTimeShortcuts.addCalendar(this);
                    $(this).blur(update);
                    $(this).change(update);
                });
                $('#dates_augmentation_table tr:last button').click(function() {
                    $(this).parents('tr').remove();
                    update();
                });
            }
            values.map(addDate);
            $('#dates_augmentation_table+a').click(function() {
                addDate();
            });
        });
    });
});
