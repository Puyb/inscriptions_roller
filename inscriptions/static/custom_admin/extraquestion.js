$(function() {
    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        $(this)
            .val(res[1])
            .hide();
    });
    // the question's own price only matters for checkboxes (choices carry
    // their own); the field is required, so give the hidden one a value
    function hidePrices() {
        if (!$('#id_prices').val()) $('#id_prices').val('0');
        $('.form-row.field-prices').hide();
    }
    function changeType() {
        var v = $('#id_type').val();
        switch(v) {
            case 'text':
                $('.form-row.field-required').show();
                hidePrices();
                $('#choices-group').hide();
                break;
            case 'radio':
            case 'list':
                $('.form-row.field-required').show();
                hidePrices();
                $('#choices-group').show();
                break;
            case 'checkbox':
                $('.form-row.field-required').hide();
                $('.form-row.field-prices').show();
                $('#choices-group').hide();
                break;
        }
    }
    $('#id_type').on('change', changeType);
    changeType();
});
