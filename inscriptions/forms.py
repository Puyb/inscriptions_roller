import json
from datetime import datetime
from pathlib import Path
from django.contrib.admin.widgets import AdminDateWidget, AdminRadioSelect
from django.forms import ModelForm, CharField, HiddenInput, Select, RadioSelect, Form, EmailField, FileField, IntegerField, ChoiceField, BooleanField
from django.forms.widgets import Textarea
from django.forms.extras.widgets import SelectDateWidget
from django.forms.formsets import formset_factory
from django.forms.models import BaseModelFormSet
from django.utils.translation import ugettext_lazy as _
from .models import Equipe, Equipier, Course, SEXE_CHOICES, JUSTIFICATIF_CHOICES 
from django.conf import settings


class EquipeForm(ModelForm):
    class Meta:
        model = Equipe
        exclude = ('paiement', 'dossier_complet', 'password', 'date', 'commentaires', 'paiement_info', 'gerant_ville2', 'numero', 'course', 'date_facture')
        widgets = {
            'categorie': HiddenInput(),
            'prix': HiddenInput(),
            'nombre': Select(choices=tuple([(i, i) for i in range(1, settings.MAX_EQUIPIERS + 1)])),
        }

class EquipierForm(ModelForm):
    class Meta:
        model = Equipier
        exclude = ('equipe', 'numero', 'piece_jointe_valide', 'autorisation_valide', 'ville2', 'code_eoskates')
        widgets = {
            'sexe':              Select(choices=SEXE_CHOICES),
            'date_de_naissance': SelectDateWidget(years=range(datetime.now().year , datetime.now().year - 100, -1)),
            'justificatif':      RadioSelect(choices=JUSTIFICATIF_CHOICES),
        }

EquipierFormset = formset_factory(EquipierForm, formset=BaseModelFormSet, extra=settings.MAX_EQUIPIERS)
EquipierFormset.model = Equipier

with (Path(settings.PACKAGE_ROOT) / 'static' / 'course_models.json').open() as f:
    COURSE_MODELS = json.load(f)

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
        widget=AdminRadioSelect(
            choices=[(k, v['_name']) for k, v in COURSE_MODELS.items()]
        )
    )
    course_prix = CharField(widget=HiddenInput)

    def save(self, commit=True):
        model = self.cleaned_data['course_model']
        prix = json.loads(self.cleaned_data['course_prix'])
        for c in COURSE_MODELS[model]['categories']:
            if c['code'] in prix:
                c['prix1'] = prix[c['code']]['prix1']
                c['prix2'] = prix[c['code']]['prix2']

        instance = super().save(commit=False)
        instance.is_active = False
        instance.save()

        for key, items in COURSE_MODELS[model].items():
            if key.startswith('_'):
                continue
            for item in items:
                getattr(instance, key).create(**item)
        return instance

class ContactForm(Form):
    name = CharField()
    email = EmailField()
    message = CharField(widget=Textarea())

class ImportResultatForm(Form):
    csv = FileField()
    skip_first = BooleanField(required=False)
    dossard_column = IntegerField()
    time_column = IntegerField(required=False)
    time_format = ChoiceField(choices=(('float', _('Nombre de secondes')), ('HMS', _('HH:MM:SS.xxx'))))
    tours_column = IntegerField(required=False)
    position_generale_column = IntegerField(required=False)
    position_categorie_column = IntegerField(required=False)

