$(function() {
    COURSE_MODEL = {};
    $.ajax('../models/' + location.search, {
        dataType: 'json',
        success: function(r) {
            COURSE_MODEL = r;
            const field = $('#id_course_model');
            let i = 0;
            // `_order` : editions precedentes (la plus recente d'abord) puis modeles ;
            // les cles numeriques d'un objet JS seraient sinon triees par id.
            const ordre = (r._order || Object.keys(r)).filter(k => k[0] !== '_');
            for (const k of ordre) {
                const v = r[k];
                if (k === '_order' || !v) continue;
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
            if (r._preselect && !$('[name=course_model]:checked').length) {
                $('[name=course_model]').first().prop('checked', true);  // edition precedente par defaut
            }
            generate_prices($('[name=course_model]:checked').val());
        }
    });
    var $place = $('<div>');
    $('fieldset')
        .append($('<div class="form-row form-prices">')
            .append($('<label class="required">').html('Tarifs&nbsp;:'))
            .append($place)
        );

    // identifiant d'edition propose : l'annee de la date, tant que l'utilisateur n'y a pas touche
    $('#id_uid').on('input', function() { $(this).data('manuel', true); });
    $('[name=date]').on('change blur', function() {
        const uid = $('#id_uid');
        if (!uid.length || uid.data('manuel') || (uid.val() && !uid.data('auto'))) return;
        const m = /(\d{4})-\d{2}-\d{2}$|\d{2}\/\d{2}\/(\d{4})$/.exec(this.value);
        if (m) uid.val(m[1] || m[2]).data('auto', true);
    });

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
                // value typed by the user if any, else the model's, else the previous step's
                const pick = (field, i) => {
                    const mine = c.code in previous ? previous[c.code][field][i] : undefined;
                    return mine !== undefined ? mine : c[field][i];
                };
                const lastPriceBase = pick('prices_base', 0);
                const lastPriceEquipier = pick('prices_equipier', 0);
                const tr = $('<tr>');
                tr.append($('<th>').html(c.code))
                tr.append($('<td>').html(c.nom))
                tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_base__0').val(lastPriceBase)));
                tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_equipier__0').val(lastPriceEquipier)));
                let previousBase = lastPriceBase;
                let previousEquipier = lastPriceEquipier;
                for (let i = 1; i <= datesAugmentations.length; i++) {
                    previousBase = pick('prices_base', i) || previousBase;
                    previousEquipier = pick('prices_equipier', i) || previousEquipier;
                    tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_base__' + i).val(previousBase)));
                    tr.append($('<td>').append($('<input>').attr('name', c.code + '__prices_equipier__' + i).val(previousEquipier)));
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
            input.before('<table id="dates_augmentation_table"></table><p class="add-row"><a class="addlink" href="#">Ajouter une date d\'augmentation</a></p>')
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
                $('#dates_augmentation_table').append('<tr><td><input size="10" value="' + d + '"></td><td><a href="#" class="deletelink">Supprimer</a></td></tr>')
                $('#dates_augmentation_table tr:last input').each(function() {
                    DateTimeShortcuts.addCalendar(this);
                    $(this).blur(update);
                    $(this).change(update);
                });
                $('#dates_augmentation_table tr:last .deletelink').click(function(e) {
                    e.preventDefault();
                    $(this).parents('tr').remove();
                    update();
                });
            }
            values.map(addDate);
            $('#dates_augmentation_table + .add-row a').click(function(e) {
                e.preventDefault();
                addDate();
            });
        });
    });
});
