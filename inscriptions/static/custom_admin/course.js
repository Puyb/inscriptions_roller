$(function() {
    var mode = '';
    if(!$('#course_form').length) return;
    $('.field-stripe_public>div').append($('<div id="stripe">'));
    var change = ask => {
        var sk = $('#id_stripe_secret').val();
        var pk = $('#id_stripe_public').val();
        if (!sk) 
            return $('#stripe').text('');
        if (!/^sk_(test|live)_/.test(sk))
            return $('#stripe').text('Erreur: la clef secrète Stripe commence par sk_live_ ou sk_test_');
        mode = /^sk_test/.test(sk) ? ' (mode test)' : '';
        if (!/^pk_(live|test)_/.test(pk)) {
            return $('#stripe').text('Erreur: la clef public Stripe doit être entrée');
        }
        var url = location.origin + '/' + $('#id_uid').val() + '/stripe/webhook/';
        $.ajax('https://api.stripe.com/v1/webhook_endpoints', {
            beforeSend: function (xhr) {
                xhr.setRequestHeader ("Authorization", "Bearer " + sk );
            },
            dataType: 'json',
            error: function(r) {
                $('#stripe').text('Erreur: vérifiez la clef secrète Stripe.' + mode);
            },
            success: function(r) {
                console.log(r);
                if (r.data.some(webhook => webhook.url === url)) {
                    $('#stripe').text('Le webhook stripe est correctement installé.' + mode);
                } else {
                    $('#stripe').text('Le webhook stripe n\'est pas installé.' + mode).append($('<button type="button">').text('Installer').click(install.bind(this, ask)));
                    if (ask && confirm('Pour faire fonctionner Stripe, il faut configurer le webhook. Voulez vous que je le fasse pour vous ?'))
                        install();
                }
            }
        });
    };
    function install() {
        var sk = $('#id_stripe_secret').val();
        var url = location.origin + '/' + $('#id_uid').val() + '/stripe/webhook/';
        $.ajax('https://api.stripe.com/v1/webhook_endpoints', {
            method: 'post',
            beforeSend: function (xhr) {
                xhr.setRequestHeader ("Authorization", "Bearer " + sk );
            },
            dataType: 'json',
            data: {
                url: url,
                'enabled_events[]': '*',
            },
            error: function(r) {
                $('#stripe').text('Erreur: vérifiez la clef secrète Stripe.' + mode);
            },
            success: function(r) {
                $('#stripe').text('Le webhook stripe est correctement installé.' + mode);
            },
        });
    };
    $('#id_stripe_secret').change(change);
    $('#id_stripe_public').change(change);
    change();
});

