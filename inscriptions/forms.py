import json, re
from datetime import datetime
from pathlib import Path
from django.contrib.admin.widgets import AdminDateWidget, AdminRadioSelect
from django.core.exceptions import ValidationError
from django.forms import ModelForm, CharField, HiddenInput, Select, RadioSelect, Form, EmailField, FileField, IntegerField, ChoiceField, BooleanField, TextInput
from django.forms.widgets import Textarea, SelectDateWidget
from django.forms.formsets import formset_factory
from django.forms.models import BaseModelFormSet
from django.utils.translation import gettext_lazy as _
from .models import COURSE_FIELDS, COURSE_UID_VALIDATOR, valide_uid_course, Course, Equipe, Equipier, Edition, Challenge, ChallengeCategorie, Paiement, PaiementRepartition, Transpondeur, SEXE_CHOICES, JUSTIFICATIF_CHOICES
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from turnstile.fields import TurnstileField
import account.forms

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
        exclude = ('paiement', 'dossier_complet', 'password', 'date', 'commentaires', 'paiement_info', 'gerant_ville2', 'numero', 'course', 'date_facture', 'tours', 'temps', 'position_generale', 'position_categorie', 'extra', 'verrou', 'penalite', 'penalite_info', )
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

class CourseFieldsMixin:
    """Ajoute au formulaire d'une Edition les champs de sa Course (organisateur,
    ville, paiement...) et les enregistre sur la Course, creee si besoin."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for nom in COURSE_FIELDS:
                self.initial.setdefault(nom, getattr(self.instance.course, nom + ('_id' if nom == 'ville2' else '')))

    def validate_unique(self):
        super().validate_unique()
        uid = self.cleaned_data.get('uid')
        if uid and self.instance.course_id and Edition.objects.filter(
                course_id=self.instance.course_id, uid=uid).exclude(pk=self.instance.pk).exists():
            self.add_error('uid', _("Une édition de cette course a déjà cet identifiant."))

    def save(self, commit=True):
        instance = super().save(commit=False)
        course = instance.course if instance.course_id else Course(
            uid=self.cleaned_data.get('course_uid') or instance.uid,
            nom=self.cleaned_data.get('course_nom') or instance.nom)
        for nom in COURSE_FIELDS:
            setattr(course, nom, self.cleaned_data[nom])
        course.save()
        instance.course = course
        if commit:
            instance.save()
            self.save_m2m()
        return instance


def _champs_course():
    return {nom: Course._meta.get_field(nom).formfield() for nom in COURSE_FIELDS}


class CourseFieldsForm(ModelForm):
    """Formulaire d'edition (admin organisateur) : champs propres a l'edition.
    Les champs de la course se modifient via `CourseSettingsForm`."""

    class Meta:
        model = Edition
        exclude = ('course', )

    def validate_unique(self):
        super().validate_unique()
        uid = self.cleaned_data.get('uid')
        if uid and self.instance.course_id and Edition.objects.filter(
                course_id=self.instance.course_id, uid=uid).exclude(pk=self.instance.pk).exists():
            self.add_error('uid', _("Une édition de cette course a déjà cet identifiant."))


class CourseSettingsForm(ModelForm):
    """Formulaire de reglage de la course (admin organisateur)."""

    class Meta:
        model = Course
        fields = ('nom', 'logo') + tuple(f for f in COURSE_FIELDS if f != 'ville2') + ('ville2', )


def _un_an_plus_tard(valeur):
    try:
        return valeur.replace(year=valeur.year + 1)
    except ValueError:  # 29 fevrier
        return valeur.replace(year=valeur.year + 1, day=28)


def _champs_modele():
    # les champs declares dans un mixin simple ne sont pas collectes par ModelForm :
    # chaque formulaire concret les declare (locals().update dans son corps de classe)
    return {
        'course_model': CharField(label=_("Modèle de course"), widget=AdminRadioSelect(choices=[])),
        'course_prix': CharField(widget=HiddenInput),
    }


class ModeleEditionMixin:
    """Choix du modele d'une nouvelle edition (`course_model`) et des tarifs
    (`course_prix`) ; recopie categories, mails et questions du modele.

    `course_model` est soit l'id d'une edition existante (« reprendre l'edition
    precedente »), soit une cle de `static/course_models.json`. `user` est renseigne
    par l'admin : seules les editions auxquelles il a acces sont copiables."""
    user = None

    class Media:
        js = ('jquery-2.1.4.min.js', 'admin_create_course.js', )
        css = { 'all': ('admin_create_course.css', ) }

    def editions_copiables(self):
        qs = Edition.objects.all()
        if self.user is None:
            return qs.none()
        if not self.user.is_superuser:
            qs = qs.filter(course__accreditations__user=self.user, course__accreditations__role__gt='')
        return qs

    def clean_course_model(self):
        model = self.cleaned_data['course_model']
        if re.match('^[0-9]+$', model):
            if not self.editions_copiables().filter(id=model).exists():
                raise ValidationError(_("Modèle inconnu."))
        elif model not in self.modeles_json():
            raise ValidationError(_("Modèle inconnu."))
        return model

    @staticmethod
    def modeles_json():
        with (Path(settings.PACKAGE_ROOT) / 'static' / 'course_models.json').open() as f:
            return json.load(f)

    def copier_modele(self, instance):
        model = self.cleaned_data['course_model']
        prix = json.loads(self.cleaned_data['course_prix'])
        if re.match('^[0-9]+$', model):
            original = Edition.objects.get(id=model)
            for key in ['categories', 'templatemail_set', 'extra']:
                for obj in getattr(original, key).all():
                    obj.id = None
                    obj.course = instance
                    if key == 'categories' and obj.code in prix:
                        obj.prices_base = prix[obj.code]['prices_base']
                        obj.prices_equipier = prix[obj.code]['prices_equipier']
                    obj.save()
        else:
            modele = self.modeles_json()[model]
            for c in modele.get('categories', []):
                if c['code'] in prix:
                    c['prices_base'] = prix[c['code']]['prices_base']
                    c['prices_equipier'] = prix[c['code']]['prices_equipier']
            for key, items in modele.items():
                if key.startswith('_'):
                    continue
                for item in items:
                    getattr(instance, key).create(**item)


FORM_META_WIDGETS = {
    'date': AdminDateWidget(),
    'date_ouverture': AdminDateWidget(),
    'date_augmentation': AdminDateWidget(),
    'date_fermeture': AdminDateWidget(),
}
FORM_META_HELP_TEXTS = {
    'uid': _("""Identifiant de l'édition dans l'adresse internet de la page d'inscription, par exemple l'année (2026). Lettres minuscules, chiffres et tirets."""),
    'organisateur': _("""Nom du club ou association organisateur"""),
    'url': _("""Adresse internet pointant vers le site présentant la course"""),
    'url_reglement': _("""Adresse internet pointant vers le réglement de la course"""),
    'email_contact': _("""Email utilisée pour envoyer les emails"""),
    'texte_accueil': _("""Ce texte sera affiché sur la page d'inscription. Vous pouvez l'utiliser si vous avez un message à passer lors de l'inscription, ou vous pouvez ne pas mettre de message."""),
}


class CourseForm(CourseFieldsMixin, ModeleEditionMixin, ModelForm):
    """Creation d'une nouvelle course et de sa premiere edition."""
    locals().update(_champs_course())
    locals().update(_champs_modele())
    course_nom = CharField(label=_('Nom de la course'), max_length=200,
                           help_text=_("Par exemple « 6 Heures de Paris ». Le nom de chaque édition se règle ensuite séparément."))
    course_uid = CharField(
        label=_('Identifiant de la course'), max_length=200,
        validators=[COURSE_UID_VALIDATOR, valide_uid_course],
        help_text=_("Premier élément de l'adresse internet de la course (par exemple 6hdeparis). Lettres minuscules et chiffres uniquement, 3 caractères au moins."))
    field_order = ['course_nom', 'course_uid', 'nom', 'uid']

    def clean_course_uid(self):
        uid = self.cleaned_data['course_uid']
        if Course.objects.filter(uid=uid).exists():
            raise ValidationError(_("Une course a déjà cet identifiant."))
        return uid

    class Meta:
        model = Edition
        exclude = ('active', 'course')
        widgets = FORM_META_WIDGETS
        help_texts = FORM_META_HELP_TEXTS

    Media = ModeleEditionMixin.Media

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.save()
        course = instance.course
        if instance.logo and not course.logo:  # repli du logo pour les editions futures sans logo
            course.logo = instance.logo.name
            course.save(update_fields=['logo'])
        self.copier_modele(instance)
        return instance


class EditionForm(ModeleEditionMixin, ModelForm):
    """Creation d'une edition d'une course existante (`course`, renseigne par l'admin).
    Les champs sont preremplis d'apres la derniere edition, dates decalees d'un an."""
    course = None
    locals().update(_champs_modele())

    class Meta:
        model = Edition
        exclude = ('active', 'course')
        widgets = FORM_META_WIDGETS
        help_texts = FORM_META_HELP_TEXTS

    Media = ModeleEditionMixin.Media

    REPRISE = ('email_contact', 'url_reglement', 'limite_participants', 'delai_paiement',
               'texte_accueil', 'distance', 'lien_externe')
    REPRISE_DATES = ('date', 'date_ouverture', 'date_fermeture', 'date_age')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        precedente = self.course.derniere_edition if self.course else None
        if precedente and not self.instance.pk:
            for nom in self.REPRISE:
                self.initial.setdefault(nom, getattr(precedente, nom))
            for nom in self.REPRISE_DATES:
                valeur = getattr(precedente, nom)
                if valeur:
                    self.initial.setdefault(nom, _un_an_plus_tard(valeur))
            self.initial.setdefault('dates_augmentation', [_un_an_plus_tard(d) for d in precedente.augmentations])
            self.initial.setdefault('uid', str(_un_an_plus_tard(precedente.date).year))

    def editions_copiables(self):
        return super().editions_copiables().filter(course=self.course)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.course = self.course
        instance.save()
        self.copier_modele(instance)
        return instance

    def validate_unique(self):
        # (course, uid) est unique, mais `course` n'est pas un champ du formulaire
        super().validate_unique()
        uid = self.cleaned_data.get('uid')
        if uid and Edition.objects.filter(course=self.course, uid=uid).exclude(pk=self.instance.pk).exists():
            self.add_error('uid', _("Une édition de cette course a déjà cet identifiant."))


class ContactForm(Form):
    name = CharField()
    email = EmailField()
    subject = CharField()
    message = CharField(widget=Textarea())
    turnstile = TurnstileField(label='')

class ImportResultatForm(Form):
    delimiter = CharField(label=_('Délimiteur'), max_length=1)
    skip_first = BooleanField(label=_('Sauter la première ligne'), required=False)
    csv = FileField(label=_('Equipes - Fichier CSV'))
    dossard_column = IntegerField(label=_('Numéro équipe'))
    time_column = IntegerField(label=_('Temps'), required=False)
    time_format = ChoiceField(label=_('Format du temps'), choices=(('float', _('Nombre de secondes')), ('HMS', _('HH:MM:SS.xxx'))))
    nbtours_column = IntegerField(label=_('Tours'), required=False)
    penalite_column = IntegerField(label=_('Pénalité'), required=False)
    penalite_info_column = IntegerField(label=_('Info pénalité'), required=False)
    position_generale_column = IntegerField(label=_('Position générale'), required=False)
    position_categorie_column = IntegerField(label=_('Position catégorie'), required=False)
    nom_column = IntegerField(label=_('Nom de l\'équipe'), required=False)
    categorie_column = IntegerField(label=_('Code catégorie'), required=False)
    tours_csv = FileField(label=_('Tours - Fichier CSV'), required=False)
    tours_dossard_column = IntegerField(label=_('Dossard (tour)'), required=False)
    tours_duree_column = IntegerField(label=_('Durée (tour)'), required=False)
    tours_duree_format = ChoiceField(label=_('Format du temps'), choices=(('float', _('Nombre de secondes')), ('HMS', _('HH:MM:SS.xxx'))))
    tours_timestamp_column = IntegerField(label=_('Heure passage (tour)'), required=False)
    tours_timestamp_format = ChoiceField(label=_('Format du temps'), choices=(('float', _('Nombre de secondes')), ('HMS', _('HH:MM:SS.xxx'))))

class TranspondeurUploadForm(Form):
    mode = ChoiceField(label=_(u"Mode d'assignation"), choices=Edition.TRANSPONDEUR_MODE_CHOICES, widget=RadioSelect())
    fichier = FileField(label=_(u'Fichier des transpondeurs (1 code par ligne)'))


class DossardFondForm(ModelForm):
    class Meta:
        model = Edition
        fields = ('fond_dossard', )


class TranspondeurForm(ModelForm):
    class Meta:
        model = Transpondeur
        fields = ('numero', 'equipe', 'equipier')

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        course = course or (self.instance.course if self.instance and self.instance.pk else None)
        self.fields['equipe'].queryset = Equipe.objects.filter(course=course)
        self.fields['equipier'].queryset = Equipier.objects.filter(equipe__course=course)
        if course and course.transpondeur_mode == Edition.TRANSPONDEUR_MODE_EQUIPE:
            self.fields['equipier'].widget = HiddenInput()
            self.fields['equipier'].required = False
        elif course and course.transpondeur_mode == Edition.TRANSPONDEUR_MODE_EQUIPIER:
            self.fields['equipe'].widget = HiddenInput()
            self.fields['equipe'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('equipe') and cleaned.get('equipier'):
            raise ValidationError(_(u"Un transpondeur ne peut être assigné qu'à une équipe OU un équipier, pas les deux."))
        return cleaned


class ChallengeForm(ModelForm):
    class Meta:
        model = Challenge
        exclude = ('active', )
    class Media:
        js = ('jquery-2.1.4.min.js', 'admin_create_challenge.js', )

    course_model = CharField(
        label=_("Model de course"),
        widget=AdminRadioSelect(choices=[
            (k, v['_name']) for (k, v) in settings.MODELS_COURSES.items()
        ])
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

class SignupForm(account.forms.SignupForm):
    turnstile = TurnstileField(label='')

