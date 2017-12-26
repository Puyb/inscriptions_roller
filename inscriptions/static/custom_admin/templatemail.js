django.jQuery(function() {
    var $ = django.jQuery;
    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        console.log(res);
        $(this)
            .val(res[1])
            .parents('.form-row').hide();
    });
});
