/* global jQuery */
(function($) {
    "use strict";
    $('#navbar a').click(function(event) {
        var $this = $(this);
        if (!$this.data('name')) return;
        $('#navbar input[name=' + $this.data('name') + ']').val($this.data('value'));
        $('#navbar')[0].submit();
        event.preventDefault();
    });
})(jQuery);
