$(function() {
    const last = arr => arr[arr.length - 1];

    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        console.log(res);
        $(this)
            .val(res[1])
            .parents('.form-row').hide();
    });
    if ($('fieldset.fieldset_prix').length === 0) return;
    $('.form-row.field-prices_base, .form-row.field-prices_equipier').hide();
    var $place = $('<div>');
    $('fieldset.fieldset_prix')
        .append($('<div class="form-row form-prices">')
            .append($place)
        );
    var $table = $('<table>');
    $place.html($table);
    const tr1 = $('<tr>')
        .append($('<th>').html(''));
    const tr2 = $('<tr>')
        .append($('<th>').html('Base'));
    const tr3 = $('<tr>')
        .append($('<th>').html('Par équipier'));
    let i = 0;
    const priceBase = $('#id_prices_base').val().split(',');
    const priceEquipier = $('#id_prices_equipier').val().split(',');
    for (const d of COURSE_DATES) {
        tr1.append($('<td>').html('À partir du ' + new Date(d).toLocaleDateString()))
        tr2.append($('<td>').append($('<input>').attr('name', 'prices_base__' + i).val(priceBase[i] || last(priceBase) || 0)));
        tr3.append($('<td>').append($('<input>').attr('name', 'prices_equipier__' + i).val(priceEquipier[i] || last(priceEquipier) || 0)));
        i++;
    }
    $table.append(tr1);
    $table.append(tr2);
    $table.append(tr3);
    $table.find('input').change(save);
    function save() {
        const priceBase = Array.from($table.find('input[name^=prices_base]')).map(f => f.value).join(',');
        const priceEquipier = Array.from($table.find('input[name^=prices_equipier]')).map(f => f.value).join(',');
        $('#id_prices_base').val(priceBase);
        $('#id_prices_equipier').val(priceEquipier);
    }
    save();
});
