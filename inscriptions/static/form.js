"use strict";
/* globals COURSE, INSTANCE, CATEGORIES, UPDATE, STAFF, CHECK_URL, I18N */
/* globals Prototype, $, $$, $F, $R, Form, Event, Ajax */

if(![].map)
    Array.prototype.map = function(fn) {
        var r = [];
        for(var i = 0; i < this.length; i++)
            r.push(fn(this[i], i));
        return r;
    };

$.fn.serializeObject = function() {
    var o = {};
    var a = this.serializeArray();
    a.forEach(function(i) {
        o[i.name] = i.value;
    });
    return o;
};

var actual_part = 0;

function age(a) {
    return function(eq) {
        var b = COURSE.YEAR - parseFloat(eq.date_de_naissance_year);
        if(b !== a) return b > a;
        if(parseFloat(eq.date_de_naissance_month) !== COURSE.MONTH)
            return parseFloat(eq.date_de_naissance_month) < COURSE.MONTH;
        return parseFloat(eq.date_de_naissance_day) <= COURSE.DAY;
    };
}

function check_date(data, k) {
    var d = new Date(parseFloat(data[k + '_year']), parseFloat(data[k + '_month']) - 1, parseFloat(data[k + '_day']));
    return d.getFullYear()  === parseFloat(data[k + '_year'])  && 
            d.getMonth() + 1 === parseFloat(data[k + '_month']) &&
            d.getDate()       === parseFloat(data[k + '_day'])   ? d : undefined;
}

function serialize() {
    $('input, select').attr('disabled', false);
    var data = $('form').serializeObject();
    disable_form_if_needed();

    data.equipiers = [{}, {}, {}, {}, {}];
    data.nombre = parseFloat(data.nombre);
    for(var k in data)
        if(/^form-\d-/.test(k) && parseFloat(k.substr(5)) < data.nombre)
            data.equipiers[parseFloat(k.substr(5))][k.substr(7)] = data[k];
    data.nombre_h = data.equipiers.filter(function(i) { return i.sexe === 'H'; }).length;
    data.nombre_f = data.equipiers.filter(function(i) { return i.sexe === 'F'; }).length;
    return data;
}

function disable_form_if_needed() {
    if(STAFF) return;
    if(new Date() >= COURSE.CLOSE_DATE || COURSE.EQUIPIERS_COUNT >= COURSE.MAX_EQUIPIERS) {
        $('input, select').each(function() {
            if(this.type !== 'file' && this.type !== 'button' && this.type !== 'submit' && this.type !== 'radio' && !/num_licence$/.test(this.name))
                this.disabled = true;
        });
    }
}

function check_nom(wait) {
    var v = $('#id_nom').val();
    if (v)
        new $.ajax(CHECK_URL, {
            data: { nom: v, id: INSTANCE.ID || '0' },
            async: !wait,
            success: function(r, text) {
                if(text !== '0')
                    $('#nom_erreur').html(gettext("Ce nom d'équipe est déjà utilisé !"));
                else
                    $('#nom_erreur').html("");

            }
        });
}

function check_step(data) {
    // check values
    var ok = true;
    var prefix = '[name=';
    var test_data = data;
    var tests;
    var message = '';
    if(!actual_part) {
        tests = {
            nom:                function(k) { check_nom(true); return /^.+$/i.test(this.nom) && $('#nom_erreur').html() === ''; },
            gerant_nom:         /^.+$/i,
            gerant_prenom:      /^.+$/i,
            gerant_ville:       /^.+$/i,
            gerant_code_postal: function(k) { return this.gerant_pays === 'FR' ? /^[0-9]{4,6}$/i.test(this.gerant_code_postal) : this.gerant_code_postal.length > 0; },
            gerant_email:       /^[a-z0-9+\-\._]+@([a-z0-9\-_]+\.)+[a-z]{2,5}$/i,
            gerant_email2:      function(k) { return this.gerant_email === this.gerant_email2; },
            nombre:             function(k) {
                var nombre = this.nombre;
                if(CATEGORIES.filter(function(categorie) {
                    return categorie.min_equipiers <= nombre && nombre <= categorie.max_equipiers;
                }).length === 0) {
                    message += gettext("Désolé, il n'y a plus de place dans cette catégorie. Changez le nombre de participants.") + '\n';
                    return false;
                }
                return true;
            },
            gerant_telephone:   /^\+?[0-9]{10,15}$/i,
            connu:              /^.+$/i
        };
    } else {
        tests = {
            nom:                /^.+$/i,
            prenom:             /^.+$/i,
            sexe:               /^[HF]$/,
            ville:              /^.+$/i,
            code_postal:        function(k) { return this.pays === 'FR' ? /^[0-9]{4,6}$/i.test(this.code_postal) : this.code_postal.length > 0; },
            email:              /^[a-z0-9+\-\._]+@([a-z0-9\-_]+\.)+[a-z]{2,5}$/i,
            date_de_naissance:  function(k) { return check_date(this, k) && age(COURSE.MIN_AGE)(this); },
            justificatif:       /^(licence|certificat)$/,
            num_licence:        function(k) { return this.justificatif !== 'licence' || /^[0-9]{3,9}$/i.test(this[k]); }
        };
        prefix = '[name=form-' + (actual_part - 1) + '-';
        test_data = data.equipiers[actual_part - 1];
    }
    for(var k in tests) {
        if(tests[k].test ? tests[k].test(test_data[k]) : tests[k].call(test_data, k)) {
            $(prefix + k + ']').parents('.form-group').removeClass('has-error');
        } else {
            ok = false;
            $(prefix + k + ']').parents('.form-group').addClass('has-error');
        }
    }
    if(!ok) {
        return alert(message + gettext('Veuillez corriger les champs en rouge.'));
    }
    return ok;
}

function setup_categories(data) {
    // filter
    var actual_categories = CATEGORIES.filter(function(c) {
        return c.min_equipiers <= data.nombre && data.nombre <= c.max_equipiers
            && data.equipiers.filter(age(c.min_age)).length === data.nombre
            && ((c.sexe === 'H' && data.nombre === data.nombre_h) ||
                (c.sexe === 'F' && data.nombre === data.nombre_f) ||
                (c.sexe === 'HX' && data.nombre_h >= 1) ||
                (c.sexe === 'FX' && data.nombre_f >= 1) ||
                (c.sexe === 'X'))
            && c.valid(data);
    });
    
    if(actual_categories.length === 0) {
        $('#button_prev')[0].click();
        alert(gettext("Votre équipe n'est éligible dans aucune des catégories proposées pour cette compétition. Veuillez vous référer au réglement de la course disponible sur le site pour voir les critères de chaque catégorie."));
        return false;
    }

    // generate html
    $('#catwrapper').html(actual_categories.map(function(c) {
        var s = '<input type="radio" value="#{id}" name="categorie" id="id_categorie-#{id}"><label for="id_categorie-#{id}">#{label} - #{prix} €</label><br />';
        for(var k in c)
            s = s.replace(new RegExp('#\\{' + k + '\\}', 'g'), c[k]);
        return s
    }).join(''));

    disable_form_if_needed();

    // install handlers
    $('input[name=categorie]').on('change', function(event) {
        $('input[name=categorie]').each(function() {
            if (!this.checked) return;
            var categorie = this.value;
            var d = CATEGORIES.filter(function(c) { return c.code === categorie; })[0];
            $('#id_prix').val(d.prix);
        });
    });

    // select the categorie
    if(UPDATE) {
        if(!$('#id_categorie-' + INSTANCE.CATEGORIE).length)
            alert(gettext("Vos modifications impliquent un changement de catégorie. Veuillez sélectionner la nouvelle catégorie."));
        else
            $('#id_categorie-' + INSTANCE.CATEGORIE).attr('checked', true);
    } else {
        $('input[name=categorie]')[0].checked = true;
        $('#id_prix').val(actual_categories[0].prix);
    }

    return true;
}

function naissanceOnChange(n) {
    var data = serialize();
    var e = $('#id_form-' + n + '-autorisation').parents('.form-group')
    if(age(18)(data.equipiers[n])) {
        e.hide();
    } else {
        e.show();
    }

};
$(function() {
    $('#id_categorie').remove();

    var TOTAL_FORMS = parseFloat($('id_form-TOTAL_FORM').val())
    for(var i = 0; i < TOTAL_FORMS; i++) {
        $('#id_form-' + i + '-date_de_naissance_day').parent()[0].id = 'id_form-' + i + '-date_de_naissance';
    }
    //$('id_password').up().insert('<br /><input type="password" id="id_password2" />');
    var maxEquipier = 0;
    CATEGORIES.forEach(function(c) {
        if (c.max_equipiers > maxEquipier)
            maxEquipier = c.max_equipiers;
    });
    $('#id_nombre>option').filter(function() {
        return parseFloat(this.value) > maxEquipier;
    }).remove();
            

    $('select[name*=naissance]').on('change', function() {
        var n = this.name.split('-')[1];
        naissanceOnChange(n);
    });

    var equipier_year_max = COURSE.YEAR - COURSE.MIN_AGE;
    $('select[name*=naissance_year]>option').each(function() {
        if (parseFloat(this.value) > equipier_year_max)
            this.remove();
    });

    $('[data-id]').each(function() {
        var $this = $(this);
        $('#' + $this.attr('data-id')).parents('.col-md-9').append($this);
    });

    $('input[name*=licence]').each(function() {
        var $this = $(this);
        var $formGroup = $this.parents('.form-group');
        var id = this.id.split('-').slice(0, 2).join('-');
        $formGroup.hide()
            .next().hide();
        var handler = function() {
            if($('#' + id + '-justificatif_1')[0].checked) {
                $formGroup.show()
                    .next().show().find('label').html(gettext('Licence') + ':');
            }
            if($('#' + id + '-justificatif_2')[0].checked) {
                $formGroup.hide()
                    .next().show().find('label').html(gettext('Certificat médical') + ':');
            }
        };
        var ie = /msie/i.test(navigator.userAgent);
        $('#' + id + '-justificatif_0').parents('.radio').remove();
        $('#' + id + '-justificatif_1').on(ie ? 'click' : 'change', handler);
        $('#' + id + '-justificatif_2').on(ie ? 'click' : 'change', handler);
        handler();
    });

    var email = $('#id_gerant_email').parents('.form-group');
    var email_bis = email.clone(true);
    email_bis.find('input:first').attr("id", "id_gerant_email2");
    email_bis.find('input:first').attr('name', "gerant_email2");
    email_bis.find('label:first').attr('for', "id_gerant_email2");
    email_bis.find('label:first').html(gettext("E-mail (confirmation) :"));
    email.after(email_bis);

    $('#id_connu>*').slice(1, -1).sort(function() { return Math.random()-.5; }).detach().appendTo($('#id_connu'));

    disable_form_if_needed();

    var nom_timeout;
    $('#id_nom')
        .after($('<div id="nom_erreur">'))
        .on('keydown', function(event) {
            clearTimeout(nom_timeout);
            nom_timeout = setTimeout(check_nom, 500);
        });



    $('#part0 input')[0].focus();

    $('#button_prev').on('click', function(event) {
        $('.parts').hide();
        actual_part--;
        $('#part' + actual_part).show();
        $('#part' + actual_part + ' input')[0].focus();
        $('#button_next').show();
        $('#button_submit').hide();
        if(!actual_part) $(this).hide();
    });


    $('#button_next').on('click', function(event) {
        var data = serialize();
        if(!check_step(data)) {
            return;
        }

        // change page
        $('#button_prev').show();
        $('.parts').hide();
        actual_part++;
        if(actual_part > parseFloat($('#id_nombre').val())) {
            // last page
            $('#partlast').show();
            try {
                $('#partlast input')[0].focus();
            } catch(e) {}

            if(setup_categories(data)) {

                $('#button_next').hide();
                $('#id_form-TOTAL_FORMS').val(actual_part - 1);
                $('#button_submit').show();
            }
        } else {
            $('#part' + actual_part).show();
            $('#part' + actual_part + ' input')[0].focus();
            naissanceOnChange(actual_part - 1);
            if(actual_part === 1) {
                // copy gerant info to the first equipier
                $('[name*=gerant_]').each(function() {
                    var element2 = $('#id_form-0-' + this.name.substr('gerant_'.length));
                    if(!element2.val()) {
                        element2.val($(this).val());
                    }
                });
            }
        }
    });



    $('#button_submit').on('mousedown', function(event) {
        for(var i = actual_part; i <= TOTAL_FORMS; i++) $('#part' + i).remove();
        var categorie = $('input[name=categorie]').filter(function() { return this.checked; })[0].value;
        $('#id_prix').val(CATEGORIES.filter(function(c) { return c.id === categorie; })[0].prix);
        if(!categorie) {
            event.stopPropagation();
            alert(gettext('Vous devez choisir une catégorie'));
        }
        if(!$('#id_conditions')[0].checked) {
            event.stopPropagation();
            alert(gettext('Vous devez accépter le règlement de la compétition'));
        }
        $('input, select').each(function() {
            this.disabled = false;
        });
    });
});

if(!UPDATE) {
    if(new Date() >= COURSE.CLOSE_DATE) {
        alert("Désolé, les inscriptions sont fermées. Il n'est plus possible de s'incrire à la course");
        location.href = COURSE.URL;
    } else if(COURSE.EQUIPIERS_COUNT >= COURSE.MAX_EQUIPIERS) {
        alert("Désolé, la course est complete, il n'y a plus de place disponible.");
        location.href = COURSE.URL;
    }
}



