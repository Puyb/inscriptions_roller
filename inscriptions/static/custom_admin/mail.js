$(function() {
    $('fieldset').after($('<div>').html($('.field-message .readonly').text()))
    $('.field-message').remove();
});
