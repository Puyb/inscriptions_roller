$(function() {
    $('fieldset').after($('<div>').html($('.field-message p').text()))
    $('.field-message').remove();
});
