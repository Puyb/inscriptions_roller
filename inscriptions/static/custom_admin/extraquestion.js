django.jQuery(function() {
    var $ = django.jQuery;
    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        $(this)
            .val(res[1])
            .parents('.form-row').hide();
    });
    function changeType() {
        debugger;
        var v = $('#id_type').val();
        switch(v) {
            case 'text':
                $('#id_required').parents('.form-row').show();
                $('#id_price1').parents('.form-row').hide();
                $('#id_price2').parents('.form-row').hide();
                $('#id_#choice-group').hide();
                break;
            case 'radio':
            case 'list':
                $('#id_required').parents('.form-row').show();
                $('#id_price1').parents('.form-row').hide();
                $('#id_price2').parents('.form-row').hide();
                $('#id_#choice-group').show();
                break;
            case 'checkbox':
                $('#id_required').parents('.form-row').hide();
                $('#id_price1').parents('.form-row').hide();
                $('#id_price2').parents('.form-row').hide();
                $('#id_#choice-group').hide();
                break;
        }
    }
    $('#id_type').on('change', changeType);
    changeType();
});
