$(function() {
    function resetCookie() {
        var date = new Date();
        date.setTime(date.getTime() - (24 * 60 * 60 * 1000));
        document.cookie = "course_uid=; expires=" + date.toGMTString() + "; path=/";
    }

    if (/^\/admin\//.test(location.href))
        resetCookie();
    if (!~COURSES_UID.indexOf(COURSE_UID) && !/^\/((course\/(choose|inscriptions\/course\/add|ask)\/$)|admin)/.test(location.pathname))
        location.href = '/course/choose/';

    $('#course_chooser').change(function() {
        var v = $(this).val();
        if(v) {
            location.href = '/' + v + '/admin/';
        } else {
            resetCookie();
            location.href = '/admin/';
        }
    });
});
