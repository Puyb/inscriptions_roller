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
                for (const webhook of r.data) {
                    console.log(webhook);
                    if (webhook.url === url) {
                        if (!$('#id_stripe_endpoint_secret').val().startsWith('whsec_')) {
                            $('#stripe').text('Le webhook stripe est installé, mais sa clef de sécurité ne l\'est pas. Voullez vous le réinstaller' + mode).append($('<button type="button">').text('Réinstaller').click(install.bind(this, webhook.id)));
                            if (ask && confirm('Pour faire fonctionner Stripe, il faut reconfigurer le webhook. Voulez vous que je le fasse pour vous ?'))
                                install(webhook.id);
                            return;
                        }
                        $('#stripe').text('Le webhook stripe est correctement installé.' + mode);
                        return;
                    }
                }
                $('#stripe').text('Le webhook stripe n\'est pas installé.' + mode).append($('<button type="button">').text('Installer').click(install.bind(this)));
                if (ask && confirm('Pour faire fonctionner Stripe, il faut configurer le webhook. Voulez vous que je le fasse pour vous ?'))
                    install();
            }
        });
    };
    function install(id) {
        var sk = $('#id_stripe_secret').val();
        if (id) {
            $.ajax('https://api.stripe.com/v1/webhook_endpoints/' + id, {
                method: 'DELETE',
                beforeSend: function (xhr) {
                    xhr.setRequestHeader ("Authorization", "Bearer " + sk );
                },
                dataType: 'json',
                error: function(r) {
                    $('#stripe').text('Erreur: vérifiez la clef secrète Stripe.' + mode);
                },
            });
        }
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
                const { secret } = r;
                $('#id_stripe_endpoint_secret').val(secret);
                $('#stripe').text('Le webhook stripe est correctement installé.' + mode);
            },
        });
    };
    $('#id_stripe_secret').change(change);
    $('#id_stripe_public').change(change);
    change();
});

