django.jQuery(function() {
    var $ = django.jQuery;

    $('fieldset').after($('<div>').html($('.field-message p').text()))
    $('.field-message').remove();
});
