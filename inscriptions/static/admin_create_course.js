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
        .append($('<div class="form-row form-prices">')
            .append($('<label class="required">').html('Tarifs&nbsp;:'))
            .append($place)
        );

    $('[name=date_ouverture]').change(() => {
        generate_prices($('[name=course_model]:checked').val());
    });

    function generate_prices(model_name) {
        if (!model_name) return;
        var model = COURSE_MODEL[model_name];

        const datesAugmentations = $('[name=dates_augmentation]').val().split(',').filter(i => i);
        let dateOuverture = $('[name=date_ouverture]').val();
        if (/\d{2}\/\d{2}\/\d{4}/.test(dateOuverture)) dateOuverture = dateOuverture.split('/').reverse().join('-');
        dateOuverture = new Date(dateOuverture);
        if (isNaN(dateOuverture)) return;
        const tr = $('<tr>')
            .append($('<th rowspan="2">').html('Code'))
            .append($('<td rowspan="2">').html('Nom'))
            .append($('<td colspan="2">').html('À partir du ' + dateOuverture.toLocaleDateString()))
        const tr2 = $('<tr>')
        tr2.append($('<td>').html('Base'));
        tr2.append($('<td>').html('Par équipier'));
        for (const d of datesAugmentations) {
            tr.append($('<td colspan="2">').html('À partir du ' + new Date(d).toLocaleDateString()))
            tr2.append($('<td>').html('Base'));
            tr2.append($('<td>').html('Par équipier'));
        }
        var $table = $('<table>').append(tr);
        $table.append(tr2);
        previous = JSON.parse($('[name=course_prix]').val() || '{}');
        $place.html($table);
        if(model.categories)
            model.categories.sort((a,b) => a.code < b.code ? -1 : a.code > b.code ? 1 : 0);
            model.categories.forEach(function(c) {
                let lastPriceBase = c.code in previous ? previous[c.code].prices_base[0] : c.prices_base[0];
                let lastPriceEquipier = c.code in previous ? previous[c.code].prices_equipier[0] : c.prices_equipier[0];
                const tr = $('<tr>');
                tr.append($('<th>').html(c.code))
                tr.append($('<td>').html(c.nom))
                tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_base__0').val(lastPriceBase)));
                tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_equipier__0').val(lastPriceEquipier)));
                for (let i = 1; i <= datesAugmentations.length; i++) {
                    tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_base__' + i).val(lastPrice = ((c.code in previous ? previous[c.code].prices_base[i] : c.prices_base[i]) || lastPriceBase))));
                    tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_equipier__' + i).val(lastPrice = ((c.code in previous ? previous[c.code].prices_equipier[i] : c.prices_equipier[i]) || lastPriceEquipier))));
                }
                tr.appendTo($table);
            });
        $table.find('input').change(updateField);
        function updateField() {
            d = {};
            $table.find('input').each(function() {
                const [code, field, index] = this.name.split('__');
                const cat = d[code] = d[code] || { prices_base: [], prices_equipier: [] }
                const last = cat[field][cat[field].length - 1];
                cat[field][index] = parseFloat(this.value) || last || 0;
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
