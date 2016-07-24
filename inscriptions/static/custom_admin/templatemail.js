django.jQuery(function() {
    var $ = django.jQuery;
    $('#id_course').each(function() {
        var res = /course_id *= *(\d+)/.exec(document.cookie);
        console.log(res);
        $(this)
            .val(res[1])
            .parents('.form-row').hide();
        return;
        tinymce.init({
            selector:'#id_message',
            plugins: [
                "advlist autolink lists link image charmap print preview anchor",
                "searchreplace visualblocks code fullscreen",
                "insertdatetime media table contextmenu paste"
            ],
            convert_urls: false,
            toolbar: "insertfile undo redo | styleselect | bold italic | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | link image"
        });
    });
});
