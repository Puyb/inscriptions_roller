import json, re
from datetime import datetime
from pathlib import Path
from django.contrib.admin.widgets import AdminDateWidget, AdminRadioSelect
from django.forms import ModelForm, CharField, HiddenInput, Select, RadioSelect, Form, EmailField, FileField, IntegerField, ChoiceField, BooleanField, TextInput
from django.forms.widgets import Textarea, SelectDateWidget
from django.forms.formsets import formset_factory
from django.forms.models import BaseModelFormSet
from django.utils.translation import ugettext_lazy as _
from .models import Equipe, Equipier, Course, Challenge, ChallengeCategorie, Paiement, PaiementRepartition, SEXE_CHOICES, JUSTIFICATIF_CHOICES 
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

class ExtraModelForm(ModelForm):
    def __init__(self, *args, **kwargs):
        opts = self._meta
        extra_questions = kwargs.pop('extra_questions')
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'] = kwargs.get('initial', {})
            kwargs['initial'].update(instance.extra)
        super().__init__(*args, **kwargs)
        for extra in extra_questions:
            self.fields.update(extra.getField())
    def _post_clean(self):
        super()._post_clean()
        self.instance.extra = { k: v for k, v in self.cleaned_data.items() if k.startswith('extra') }


class EquipeForm(ExtraModelForm):
    class Meta:
        model = Equipe
        exclude = ('paiement', 'dossier_complet', 'password', 'date', 'commentaires', 'paiement_info', 'gerant_ville2', 'numero', 'course', 'date_facture', 'tours', 'temps', 'position_generale', 'position_categorie', 'extra', 'verrou', )
        widgets = {
            'categorie': HiddenInput(),
            'prix': HiddenInput(),
            'nombre': Select(choices=tuple([(i, i) for i in range(1, settings.MAX_EQUIPIERS + 1)])),
        }



class EquipierForm(ExtraModelForm):
    class Meta:
        model = Equipier
        exclude = ('equipe', 'numero', 'piece_jointe_valide', 'autorisation_valide', 'ville2', 'code_eoskates', 'extra')
        widgets = {
            'sexe':              Select(choices=SEXE_CHOICES),
            'date_de_naissance': SelectDateWidget(years=range(datetime.now().year , datetime.now().year - 100, -1)),
            'justificatif':      RadioSelect(choices=JUSTIFICATIF_CHOICES),
        }

EquipierFormset = formset_factory(EquipierForm, formset=BaseModelFormSet, extra=settings.MAX_EQUIPIERS)
EquipierFormset.model = Equipier

class CourseForm(ModelForm):
    class Meta:
        model = Course
        exclude = ('active', )
        widgets = {
            'date': AdminDateWidget(),
            'date_ouverture': AdminDateWidget(),
            'date_augmentation': AdminDateWidget(),
            'date_fermeture': AdminDateWidget(),
        }
        help_texts = {
            'uid': _("""Code utilisé pour identifier la course. Ce code sera affiché dans l'adresse internet de la page d'inscription. Par exemple, pour les 6h de Paris 2015, le code était 6hdp15. Ce code ne doit contenir que des lettres ou des chiffres."""),
            'organisateur': _("""Nom du club ou association organisateur"""),
            'url': _("""Adresse internet pointant vers le site présentant la course"""),
            'url_reglement': _("""Adresse internet pointant vers le réglement de la course"""),
            'email_contact': _("""Email utilisée pour envoyer les emails"""),
        }
    class Media:
        js = ('jquery-2.1.4.min.js', 'admin_create_course.js', )

    course_model = CharField(
        label=_("Model de course"),
        widget=AdminRadioSelect(choices=[('a', 'b')])
    )
    course_prix = CharField(widget=HiddenInput)

    def save(self, commit=True):
        model = self.cleaned_data['course_model']
        prix = json.loads(self.cleaned_data['course_prix'])
        if re.match('^[0-9]+$', model):
            course = Course.objects.get(id=model)
            original = course
            instance = super().save(commit=False)
            instance.is_active = False
            instance.save()

            for key in ['categories', 'templatemail_set', 'extra']:
                for obj in getattr(course, key).all():
                    obj.id = None
                    obj.course = instance
                    if key == 'categories':
                        if obj.code in prix:
                            obj.prix1 = prix[obj.code]['prix1']
                            obj.prix2 = prix[obj.code]['prix2']
                    obj.save()

        else:
            with (Path(settings.PACKAGE_ROOT) / 'static' / 'course_models.json').open() as f:
                models = json.load(f)

                if 'categories' in models[model]:
                    for c in models[model]['categories']:
                        if c['code'] in prix:
                            c['prix1'] = prix[c['code']]['prix1']
                            c['prix2'] = prix[c['code']]['prix2']

                instance = super().save(commit=False)
                instance.is_active = False
                instance.save()

                for key, items in models[model].items():
                    if key.startswith('_'):
                        continue
                    for item in items:
                        getattr(instance, key).create(**item)
        return instance

class ContactForm(Form):
    name = CharField()
    email = EmailField()
    subject = CharField()
    message = CharField(widget=Textarea())

class ImportResultatForm(Form):
    csv = FileField(label=_('Fichier CSV'))
    delimiter = CharField(label=_('Délimiteur'), max_length=1)
    skip_first = BooleanField(label=_('Sauter la première ligne'), required=False)
    dossard_column = IntegerField(label=_('Dossard'))
    time_column = IntegerField(label=_('Temps'), required=False)
    time_format = ChoiceField(label=_('Format du temps'), choices=(('float', _('Nombre de secondes')), ('HMS', _('HH:MM:SS.xxx'))))
    tours_column = IntegerField(label=_('Tours'), required=False)
    position_generale_column = IntegerField(label=_('Position générale'), required=False)
    position_categorie_column = IntegerField(label=_('Position catégorie'), required=False)
    nom_column = IntegerField(label=_('Nom de l\'équipe'), required=False)
    categorie_column = IntegerField(label=_('Code catégorie'), required=False)

class ChallengeForm(ModelForm):
    class Meta:
        model = Challenge
        exclude = ('active', )
    class Media:
        js = ('jquery-2.1.4.min.js', 'admin_create_challenge.js', )

    course_model = CharField(
        label=_("Model de course"),
        widget=AdminRadioSelect(choices=[])
    )

    def save(self, commit=True):
        model = self.cleaned_data['course_model']
        instance = super().save(commit=False)
        instance.save()

        with (Path(settings.PACKAGE_ROOT) / 'static' / 'course_models.json').open() as f:
            models = json.load(f)
            fields = [ f.name for f in ChallengeCategorie._meta.get_fields() ]
            for cat in models[model]['categories']:
                instance.categories.create(**{ k: v for k, v in cat.items() if k in fields })
        return instance

class AdminPaiementForm(ModelForm):
    class Meta:
        model = Paiement
        fields = ('type', 'montant', 'montant_frais', 'detail')
    initials = {
        'type': 'chèque',
    }
    type = CharField(
        label=_("Type de paiement"),
        widget=AdminRadioSelect(
            choices=Paiement.MANUAL_TYPE_CHOICES
        ),
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.type in ('stripe', 'paypal'):
            self.fields['type'].widget = TextInput()
            for field in ('type', 'montant', 'montant_frais', 'detail'):
                self.fields[field].widget.attrs['readonly'] = True
        self.fields['montant_frais'].widget.attrs['readonly'] = True
