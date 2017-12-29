$(function() {
    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        $(this)
            .val(res[1])
            .hide();
    });
    function changeType() {
        var v = $('#id_type').val();
        switch(v) {
            case 'text':
                $('.form-row.field-required').show();
                $('.form-row.field-price1').hide();
                $('.form-row.field-price2').hide();
                $('#choices-group').hide();
                break;
            case 'radio':
            case 'list':
                $('.form-row.field-required').show();
                $('.form-row.field-price1').hide();
                $('.form-row.field-price2').hide();
                $('#choices-group').show();
                break;
            case 'checkbox':
                $('.form-row.field-required').hide();
                $('.form-row.field-price1').show();
                $('.form-row.field-price2').show();
                $('#choices-group').hide();
                break;
        }
    }
    $('#id_type').on('change', changeType);
    changeType();
});
