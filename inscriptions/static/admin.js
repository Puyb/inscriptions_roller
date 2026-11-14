$(function() {
    function resetCookie() {
        var date = new Date();
        date.setTime(date.getTime() - (24 * 60 * 60 * 1000));
        document.cookie = "course_uid=; expires=" + date.toGMTString() + "; path=/";
    }

    if (/^\/admin\//.test(location.pathname))
        resetCookie();
    if (COURSES_UID !== false && !~COURSES_UID.indexOf(COURSE_UID) && !/^\/((course\/(login|choose|inscriptions\/course\/add|ask)\/$)|admin)/.test(location.pathname))
        location.href = '/course/choose/';
});
