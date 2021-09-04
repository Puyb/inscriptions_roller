# -*- coding: utf-8 -*-
from collections import defaultdict
from operator import itemgetter
from django.utils.translation import ugettext_lazy as _
from django_countries.fields import CountryField
from django.conf import settings
from django.template.loader import render_to_string
from django.core.validators import RegexValidator
from django.template import Template, Context
import os, re, requests, json, sys
from django.db import models, transaction
from django.db.models.query import prefetch_related_objects
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db.models import Count, Sum, Value, F, Q, When, Case, Prefetch, Func, Min
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce, Lower
from django.contrib.sites.models import Site
from .utils import iriToUri, send_mail, ChallengeInscriptionEquipe
from django import forms
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.models import ContentType
import logging
import traceback
import pytz
import uuid
from Levenshtein import distance

logger = logging.getLogger(__name__)

class NoPlaceLeftException(Exception):
    pass

SEXE_CHOICES = (
    ('H', _(u'Homme')),
    ('F', _(u'Femme')),
)

MIXITE_CHOICES = (
    ('H', _(u'Homme')),
    ('F', _(u'Femme')),
    ('HX', _(u'Homme ou Mixte')),
    ('FX', _(u'Femme ou Mixte')),
    ('X', _(u'Mixte')),
    ('', _(u'Sans critères')),
)

JUSTIFICATIF_CHOICES = (
    ('licence',    _(u'Licence FFRS')),
    ('certificat', _(u'Certificat médical')),
)

ROLE_CHOICES = (
    ('', _(u'Accès interdit')),
    ('admin', _(u'Administrateur')),
    ('organisateur', _(u'Organisateur')),
    ('validateur', _(u'Validateur')),
)

DESTINATAIRE_CHOICES = (
    ('Equipe', _(u"Gerant d'équipe")),
    ('Equipier', _(u'Equipier')),
    ('Organisateur', _(u'Organisateur')),
    ('Tous', _(u'Tous')),
)

#class Chalenge(model.Model):
#    nom = models.CharField(_('Nom'), max=200)

def normalize_club(club):
    club = club.upper().strip()
    table = {
        u'': u'Aucun',
        u'-': u'Aucun',
        u'INDÉPENDANT': u'Aucun',
        u'INDéPENDANT': u'Aucun',
    }
    return table.get(club, club)

class Course(models.Model):
    nom                 = models.CharField(_(u'Nom'), max_length=200)
    uid                 = models.CharField(_(u'uid'), max_length=200, validators=[RegexValidator(regex="^[a-z0-9]{3,}$", message=_("Ne doit contenir que des lettres ou des chiffres"))], unique=True)
    organisateur        = models.CharField(_(u'Organisateur'), max_length=200)
    ville               = models.CharField(_(u'Ville'), max_length=200)
    date                = models.DateField(_(u'Date'))
    url                 = models.URLField(_(u'URL'))
    url_reglement       = models.URLField(_(u'URL Réglement'))
    email_contact       = models.EmailField(_(u'Email contact'))
    logo                = models.ImageField(_('Logo'), upload_to='logo', null=True, blank=True)
    date_ouverture      = models.DateField(_(u"Date d'ouverture des inscriptionss"))
    date_augmentation   = models.DateField(_(u"Date d'augmentation des tarifs"), null=True, blank=True)
    date_fermeture      = models.DateField(_(u"Date de fermeture des inscriptions"))
    limite_participants = models.DecimalField(_(u"Limite du nombre de participants"), max_digits=6, decimal_places=0)
    paypal              = models.EmailField(_(u'Adresse paypal'), blank=True)
    frais_paypal_inclus = models.BooleanField(_(u'Frais paypal inclus'))
    stripe_secret       = models.CharField(_('Stripe Secret Key'), max_length=200, blank=True, null=True)
    stripe_public       = models.CharField(_('Stripe Public Key'), max_length=200, blank=True, null=True)
    stripe_endpoint_secret = models.CharField(_('Stripe End Point Secret'), max_length=200, blank=True, null=True)
    frais_stripe_inclus = models.BooleanField(_(u'Frais stripe inclus'))
    ordre               = models.CharField(_(u'Ordre des chèques'), max_length=200)
    adresse             = models.TextField(_(u'Adresse'), blank=True)
    active              = models.BooleanField(_(u'Activée'), default=False)
    distance            = models.DecimalField(_(u'Distance d\'un tour (en km)'), max_digits=6, decimal_places=3, blank=True, null=True)

    @property
    def ouverte(self):
        return self.active and self.date_ouverture <= date.today()

    @property
    def fermee(self):
        return not self.active or self.date_fermeture <= date.today()

    @property
    def dernier_jour_inscription(self):
        return self.date_fermeture - timedelta(days=1)

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = self.nom.lower().replace(' ', '_')
        if not self.id:
            send_mail(
                subject='Nouvelle course %s' % self.nom,
                body="""%s.
""" % self.nom,
                to=(('', settings.CONTACT_MAIL), ),
                content_type='plain',
            )
        if self.active and self.id  and not Course.objects.get(id=self.id).active:
            send_mail(
                subject='Votre course %s est activée' % self.nom,
                body="""Votre course %s est activée.
Les inscriptions pourront commencer à la date que vous avez choisi.
""" % self.nom,
                to=[self.email_contact],
                content_type='text',
            )
        super(Course, self).save(*args, **kwargs)

    def __str__(self):
        return '%s (%s)' % (self.nom, self.date)

    def send_mail(self, nom, instances):
        mail = TemplateMail.objects.select_related('course').get(course=self, nom=nom)
        mail.send(instances)

    @property
    def date_certificat(self):
        return self.date - timedelta(days=365)

    @property
    def date_certificat_3ans(self):
        return self.date - timedelta(days=365 * 3)

    def stats(self):
        model_stats = {
            "equipes": 0,
            "equipiers": 0,
            "hommes": 0,
            "femmes": 0,
            "paiement": 0,
            "prix": 0,
            "reste_a_payer": 0,
            "nbcertifenattente": 0,
            "documents": 0,
            "documents_electroniques": 0,
            "documents_attendus": 0,
            "p": 0,
            "pc": 0,
            "pi": 0,
            "pe": 0,
            "pv": 0,
            "ip": 0,
            "ipc": 0,
            "ipi": 0,
            "ipe": 0,
            "ipv": 0,
        }
        for categorie in Categorie.objects.all():
            model_stats[categorie.code] = 0
        result = {
            "categories": {},
            "jours": {},
            "pays": {},
            "course": model_stats.copy(),
            "clubs": {},
        }

        equipes = (Equipe.objects.filter(course=self)
            .annotate(
                equipiers_count=Count('equipier'),
                verifier_count=Coalesce(Sum(Case(When(equipier__verifier=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                licence_manquantes_count=Coalesce(Sum(Case(When(equipier__licence_manquante=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                certificat_manquants_count=Coalesce(Sum(Case(When(equipier__certificat_manquant=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                autorisation_manquantes_count=Coalesce(Sum(Case(When(equipier__autorisation_manquante=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                valide_count=Coalesce(Sum(Case(When(equipier__valide=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                erreur_count=Coalesce(Sum(Case(When(equipier__erreur=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
                hommes_count=Coalesce(Sum(Case(When(equipier__homme=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            ).select_related('categorie', 'gerant_ville2')
            .prefetch_related('equipier_set')
            .prefetch_related('equipier_set__equipe')
            .prefetch_related('equipier_set__equipe__course')
        )
        montants_equipes = {
            equipe.id: equipe._montant_paiements
            for equipe in Equipe.objects.filter(course=self).annotate(
                _montant_paiements=Sum(Case(When(paiements__paiement__montant__isnull=False, then=F('paiements__montant')), default=Value(0), output_field=models.DecimalField(max_digits=7, decimal_places=2)))
            )
        }
        tz = pytz.timezone('Europe/Paris')
        for equipe in equipes:
            equipe._montant_paiements = montants_equipes[equipe.id]
            stats = model_stats.copy()
            keys = {
                "categories": equipe.categorie_id and equipe.categorie.code or '',
                "jours": (equipe.date.astimezone(tz).date() - self.date_ouverture).days,
                "pays":    '',
                "clubs": normalize_club(equipe.club),
            }
            if equipe.gerant_ville2:
                keys['pays'] = equipe.gerant_ville2.pays
                if equipe.gerant_ville2.pays == 'FR':
                    keys['pays'] = equipe.gerant_ville2.region

                    
            stats['equipes'] = 1
            stats['equipiers'] = equipe.equipiers_count
            stats['hommes'] = equipe.hommes_count
            stats['femmes'] = equipe.equipiers_count - equipe.hommes_count
            token = ''
            if not equipe.paiement_complet():
                token += 'i'
                stats['ip'] += 1
            else:
                stats['p'] += 1
            token += 'p';
            if equipe.verifier():
                token += 'v'
            else:
                if equipe.dossier_complet_auto() == False:
                    token += "e"
                elif equipe.dossier_complet_auto() == None:
                    token += "i"
                else:
                    token += 'c'
            stats[token] = 1

            stats['paiement'] = float(equipe.montant_paiements)
            stats['prix'] = float(equipe.prix)
            stats['reste_a_payer'] = float(equipe.reste_a_payer)
            stats['nbcertifenattente'] = equipe.licence_manquantes_count + equipe.certificat_manquants_count + equipe.autorisation_manquantes_count
            stats[equipe.categorie.code] += 1;

            for key, index in keys.items():
                if index not in result[key]:
                    result[key][index] = model_stats.copy();
                    if equipe.gerant_ville2:
                        if key == 'pays':
                            result[key][index]['pays'] = equipe.gerant_ville2.pays

                for stat, value in stats.items():
                    result[key][index][stat] += value
            for stat, value in stats.items():
                result['course'][stat] += value

        result['villes'] = [
            {
                'nom': ville.nom,
                'pays': ville.pays,
                'lat': float(ville.lat),
                'lng': float(ville.lng),
                'count': ville.count,
            } for ville in Ville.objects.filter(equipier__equipe__course=self).annotate(count=Coalesce(Sum('equipe__nombre'), Value(0)))
            if ville.count > 0 ]
        sorted(result['villes'], key=itemgetter('nom'))
        sorted(result['villes'], key=itemgetter('count'), reverse=True)

        result['course']['documents'] = 0
        result['course']['documents_electroniques'] = 0
        result['course']['documents_attendus'] = 0
        result['course']['licencies'] = 0
        for equipier in Equipier.objects.filter(equipe__course=self).select_related('equipe', 'equipe__course'):
            if equipier.piece_jointe_valide:
                result['course']['documents'] += 1
                if equipier.piece_jointe:
                    result['course']['documents_electroniques'] += 1
            else:
                result['course']['documents_attendus'] += 1
            if equipier.age() < 18:
                if equipier.autorisation_valide:
                    result['course']['documents'] += 1
                    if equipier.autorisation:
                        result['course']['documents_electroniques'] += 1
                else:
                    result['course']['documents_attendus'] += 1
            if equipier.justificatif == 'licence':
                result['course']['licencies'] +=1

        return result

    def equipiers_commun(self, course2):
        equipiers = Equipier.objects.annotate(
            n=Unaccent(Lower(RegexpReplace('nom', Value('[ -]\\+'), Value(' ')))),
            p=Unaccent(Lower(RegexpReplace('prenom', Value('[ -]\\+'), Value(' ')))),
        )
        equipiers1 = equipiers.filter(equipe__course=self)
        if isinstance(course2, Course):
            equipiers2 = equipiers.filter(equipe__course=course2)
        else:
            equipiers2 = equipiers.filter(equipe__course__in=course2)

        doublons = defaultdict(lambda: [])
        for e in equipiers1:
            if e.numero > e.equipe.nombre:
                continue
            for e2 in equipiers2:
                if e2.numero > e2.equipe.nombre:
                    continue
                if distance(e.n, e2.n) < 3 and distance(e.p, e2.p) < 3:
                    doublons[e].append(e2)

        return doublons

class Categorie(models.Model):
    course          = models.ForeignKey(Course, related_name='categories', on_delete=models.CASCADE)
    nom             = models.CharField(_(u'Nom'), max_length=200)
    code            = models.CharField(_(u'Code'), max_length=200)
    prix1           = models.DecimalField(_(u"Prix normal"), max_digits=7, decimal_places=2)
    prix2           = models.DecimalField(_(u"Prix augmenté"), max_digits=7, decimal_places=2)
    min_equipiers   = models.IntegerField(_(u"Nombre minimum d'équipiers"))
    max_equipiers   = models.IntegerField(_(u"Nombre maximum d'équipiers"))
    min_age         = models.IntegerField(_(u'Age minimum'), default=12)
    sexe            = models.CharField(_(u'Sexe'), max_length=2, choices=MIXITE_CHOICES, blank=True)
    validation      = models.TextField(_(u'Validation function (javascript)'))
    numero_debut    = models.IntegerField(_(u'Numero de dossard (début)'), default=0)
    numero_fin      = models.IntegerField(_(u'Numero de dossard (fin)'), default=0)

    def __str__(self):
        return self.code

    def prix(self, d=None):
        if isinstance(d, datetime):
            d = d.date()
        d = d or date.today()
        prix = self.prix1 or 0
        if self.course.date_augmentation and self.course.date_augmentation <= d:
            prix = self.prix2 or 0
        return prix


class Ville(models.Model):
    lat      = models.DecimalField(max_digits=10, decimal_places=7)
    lng      = models.DecimalField(max_digits=10, decimal_places=7)
    nom      = models.CharField(max_length=200)
    region   = models.CharField(max_length=200)
    pays     = models.CharField(max_length=200)

def lookup_ville(nom, cp, pays):
    nom = nom.lower()
    nom = re.sub('[- ,/]+', ' ', nom)
    try:
        return Ville.objects.get(nom=nom)
    except Ville.DoesNotExist as e:
        pass
    except Ville.MultipleObjectsReturned as e:
        pass

    try:
        response = requests.get(iriToUri('http://open.mapquestapi.com/geocoding/v1/address?key=%s&location=%s' % (settings.MAPQUEST_API_KEY, nom + ' ' + cp + ', ' + str(pays))))
        data = response.json()

        if('results' not in data or
           not len(data['results']) or
           'locations' not in data['results'][0] or
           not len(data['results'][0]['locations']) or
           data['results'][0]['locations'][0].get('adminArea5', '') == ''
           ):
            response = requests.get(iriToUri('http://open.mapquestapi.com/geocoding/v1/address?key=%s&location=%s' % (settings.MAPQUEST_API_KEY, nom + ', ' + str(pays))))
            data = response.json()

            if('results' not in data or
               not len(data['results']) or
               'locations' not in data['results'][0] or
               not len(data['results'][0]['locations']) or
               data['results'][0]['locations'][0].get('adminArea5', '') == ''
               ):
                return None

        data = data['results'][0]['locations'][0]
        data['latLng']['lat'] = str(data['latLng']['lat'])
        data['latLng']['lng'] = str(data['latLng']['lng'])
        try:
            return Ville.objects.get(lat=data['latLng']['lat'], lng=data['latLng']['lng'])
        except Ville.DoesNotExist as e:
            pass
        obj = Ville(
            lat      = data['latLng']['lat'],
            lng      = data['latLng']['lng'],
            nom      = data['adminArea5'],
            region   = data['adminArea3'],
            pays     = data['adminArea1']
        )
        obj.save()
        return obj
    except ValueError as e:
        print(response.text)
        traceback.print_exc()
    except Exception as e:
        traceback.print_exc()
        return None

class Equipe(models.Model):
    nom                = models.CharField(_(u"Nom d'équipe"), max_length=30)
    club               = models.CharField(_(u'Club'), max_length=30, blank=True)
    gerant_nom         = models.CharField(_(u'Nom'), max_length=200)
    gerant_prenom      = models.CharField(_(u'Prénom'), max_length=200)
    gerant_adresse1    = models.CharField(_(u'Adresse'), max_length=200, blank=True)
    gerant_adress2     = models.CharField(_(u'Adresse 2'), max_length=200, blank=True)
    gerant_ville       = models.CharField(_(u'Ville'), max_length=200)
    gerant_code_postal = models.CharField(_(u'Code postal'), max_length=200)
    gerant_pays        = models.CharField(_(u'Pays'), max_length=2, default='FR')
    gerant_email       = models.EmailField(_(u'e-mail'), max_length=200)
    password           = models.CharField(_(u'Mot de passe'), max_length=200, blank=True)
    gerant_telephone   = models.CharField(_(u'Téléphone'), max_length=200, blank=True)
    categorie          = models.ForeignKey(Categorie, on_delete=models.CASCADE)
    course             = models.ForeignKey(Course, on_delete=models.CASCADE)
    nombre             = models.IntegerField(_(u"Nombre d'équipiers"))
    prix               = models.DecimalField(_(u'Prix'), max_digits=5, decimal_places=2)
    dossier_complet    = models.NullBooleanField(_(u'Dossier complet'))
    date               = models.DateTimeField(_(u"Date d'insciption"), auto_now_add=True)
    commentaires       = models.TextField(_(u'Commentaires'), blank=True)
    gerant_ville2      = models.ForeignKey(Ville, null=True, on_delete=models.SET_NULL)
    numero             = models.IntegerField(_(u'Numéro'))
    date_facture       = models.DateField(_('Date facture'), blank=True, null=True)
    tours              = models.IntegerField(_('Nombre de tours'), blank=True, null=True)
    temps              = models.DecimalField(_('Temps (en secondes)'), max_digits=9, decimal_places=3, null=True, blank=True)
    position_generale  = models.IntegerField(_('Position générale'), blank=True, null=True)
    position_categorie = models.IntegerField(_('Position catégorie'), blank=True, null=True)
    extra              = JSONField(default={})
    verrou             = models.BooleanField(_('Equipe verrouillée (modifiable uniquement par l\'organisateur)'), default=False)

    class Meta:
        unique_together = ( ('course', 'numero'), )

    def __str__(self):
        return u'%s - %s - %s - %s' % (self.numero, self.course.uid, self.categorie, self.nom)

    def licence_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.numero <= self.numero and equipier.licence_manquante]

    def certificat_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.numero <= self.numero and equipier.certificat_manquant]

    def autorisation_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.numero <= self.numero and equipier.autorisation_manquante]

    def verifier(self):
        if hasattr(self, 'verifier_count'):
            return self.verifier_count > 0
        return len([equipier for equipier in self.equipier_set.all().filter(numero__lte=self.nombre) if equipier.verifier]) > 0

    def dossier_complet_auto(self):
        if hasattr(self, 'erreur_count'):
            if self.erreur_count > 0:
                return False
        elif len([equipier for equipier in self.equipier_set.filter(numero__lte=self.nombre) if equipier.erreur]) > 0:
            return False
        if hasattr(self, 'valide_count'):
            if self.valide_count < self.nombre:
                return None
        elif len([equipier for equipier in self.equipier_set.filter(numero__lte=self.nombre) if not equipier.valide]) > 0:
            return None
        return True

    @property
    def montant_paiements(self):
        if hasattr(self, '_montant_paiements'):
            return self._montant_paiements or Decimal(0)
        return self.paiements.filter(paiement__montant__isnull=False).aggregate(sum=Sum('montant'))['sum'] or Decimal(0)

    @property
    def montant_frais(self):
        if hasattr(self, '_montant_frais'):
            return self._montant_frais or Decimal(0)
        return self.paiements.filter(paiement__montant__isnull=False).aggregate(sum=Sum('montant_frais'))['sum'] or Decimal(0)

    @property
    def reste_a_payer(self):
        return self.prix - self.montant_paiements

    def paiement_complet(self):
        return self.montant_paiements >= self.prix

    @property
    def paiements_en_attente(self):
        return Decimal('0.00');
        # return self.paiements.filter(montant__isnull=True).aggregate(sum=Sum('strip_charge__amount'))['sum'] or Decimal(0)

    def paiement_complet_en_attente(self):
        montant = self.montant_paiements
        montant += self.paiements_en_attente
        return montant >= self.prix

    def facture(self):
        lines = [
            {
                'quantite': 1,
                'label': '%s - %s' % (self.categorie.code, self.categorie.nom),
                'prix_unitaire': self.categorie.prix(self.date),
                'prix': self.categorie.prix(self.date),
            },
        ]
        extra_equipiers = self.equipier_set.values('extra')
        for extra in self.course.extra.exclude(type='text'):
            values = []
            if extra.page == 'Equipier':
                values = [ v['extra'][extra.getId()] for v in extra_equipiers if extra.getId() in v['extra'] ]
            else:
                if extra.getId() in self.extra:
                    values.append(self.extra[extra.getId()])
            if extra.type == 'checkbox' and extra.price(self.date):
                values = [ v for v in values if v ]
                if len(values):
                    lines.append({
                        'quantite': len(values),
                        'label': extra.label,
                        'prix_unitaire': extra.price(self.date),
                        'prix': extra.price(self.date) * len(values),
                    })
            else:
                options = defaultdict(int)
                for value in values:
                    options[value] += 1
                for option, count in options.items():
                    price = extra.getPriceByValue(self.date, option)
                    if price:
                        lines.append({
                            'quantite': count,
                            'label': '%s - %s' % (extra.label, option),
                            'prix_unitaire': price,
                            'prix': price * count,
                        })
        return lines
        
    def save(self, *args, **kwargs):
        if self.id:
            if not self.verrou and self.course.date >= date.today():
                if not (self.categorie.numero_debut <= self.numero and self.numero <= self.categorie.numero_fin):
                    self.numero = self.getNumero()
                    try:
                        self.send_mail('changement_numero')
                    except Exception as e:
                        traceback.print_exc()
                    try:
                        self.send_mail('changement_numero_admin')
                    except Exception as e:
                        traceback.print_exc()
        else:
            if not self.numero:
                self.numero = self.getNumero()

        if not self.gerant_ville2_id:
            self.gerant_ville2 = lookup_ville(self.gerant_ville, self.gerant_code_postal, self.gerant_pays)
        return super(Equipe, self).save(*args, **kwargs)


    def send_mail(self, nom):
        self.course.send_mail(nom, [self])

    def getNumero(self):
        start = self.categorie.numero_debut
        end = self.categorie.numero_fin

        res = Equipe.objects.raw("""SELECT e1.id as id, e1.numero as numero FROM inscriptions_equipe e1 
                LEFT JOIN inscriptions_equipe e2 ON e1.numero=e2.numero-1 AND e1.course_id=e2.course_id
                WHERE e1.course_id=%s AND e1.numero>=%s AND e1.numero<=%s AND e2.numero IS NULL ORDER BY 2 LIMIT 1""", 
                [self.course.id, start, end])
        res = list(res)

        if len(res) == 0 or res[0].numero == None:
            numero = start
        else:
            numero = res[0].numero + 1
        if numero > end:
            raise NoPlaceLeftException
        return numero

    @property
    def date_annulation(self):
        return min(self.date.date() + timedelta(days=31), self.course.date)

    def temps_humain(self):
        if not self.temps:
            return ''
        s = []
        t = self.temps
        while t:
            f = ('%06' if not s else '%02') if t > 60 else '%'
            f += 'd' if s else '.3f'
            s.append(f % (t % 60))
            t = (t // 60).to_integral()
        s.reverse()
        return ':'.join(s)

    def cookie_key(self):
        return 'code_%s' % self.id

    def distance(self):
        return self.tours * self.course.distance if self.tours else None

class Equipier(models.Model):
    CERTIFICAT_HELP = _("""Si vous le pouvez, scannez le certificat et ajoutez le en pièce jointe (formats PDF ou JPEG).
Vous pourrez aussi le télécharger plus tard, ou l'envoyer par courrier (%(link)s). Votre certificat doit avoir moins d'un an au moment de la course.""")
    LICENCE_HELP = _("""Si vous le pouvez, scannez la licence et ajoutez la en pièce jointe (formats PDF ou JPEG).
Vous pourrez aussi le télécharger plus tard, ou l'envoyer par courrier.""")
    AUTORISATION_HELP = _("""Si vous le pouvez, scannez l'autorisation et ajoutez la en pièce jointe (formats PDF ou JPEG).
Vous pourrez aussi la télécharger plus tard, ou l'envoyer par courrier (%(link)s)""")
    DATE_DE_NAISSANCE_HELP = _("""Chaque équipier doit avoir plus de %(min_age)s ans au %(date)s.""")
    JUSTIFICATIF_HELP = _("""Chaque équipier doit avoir un certificat médical de moins d'un an ou une licence FFRS en cours de validité pour participer.""")

    numero            = models.IntegerField(_(u'Numéro'))
    equipe            = models.ForeignKey(Equipe, on_delete=models.CASCADE)
    nom               = models.CharField(_(u'Nom'), max_length=200)
    prenom            = models.CharField(_(u'Prénom'), max_length=200, blank=True)
    sexe              = models.CharField(_(u'Sexe'), max_length=1, choices=SEXE_CHOICES)
    adresse1          = models.CharField(_(u'Adresse'), max_length=200, blank=True)
    adresse2          = models.CharField(_(u'Adresse'), max_length=200, blank=True)
    ville             = models.CharField(max_length=200)
    code_postal       = models.CharField(max_length=200)
    pays              = models.CharField(_(u'Pays'), max_length=2, default='FR')
    email             = models.EmailField(_(u'e-mail'), max_length=200, blank=True)
    date_de_naissance = models.DateField(_(u'Date de naissance'), help_text=DATE_DE_NAISSANCE_HELP)
    autorisation      = models.FileField(_(u'Autorisation parentale'), upload_to='certificats', blank=True, help_text=AUTORISATION_HELP)
    autorisation_valide  = models.NullBooleanField(_(u'Autorisation parentale valide'))
    justificatif      = models.CharField(_(u'Justificatif'), max_length=15, choices=JUSTIFICATIF_CHOICES, help_text=JUSTIFICATIF_HELP)
    num_licence       = models.CharField(_(u'Numéro de licence'), max_length=15, blank=True)
    piece_jointe      = models.FileField(_(u'Certificat ou licence'), upload_to='certificats', blank=True)
    piece_jointe_valide  = models.NullBooleanField(_(u'Certificat ou licence valide'))
    ville2            = models.ForeignKey(Ville, null=True, on_delete=models.SET_NULL)
    extra             = JSONField(default={})

    # Pre-calculated fields
    verifier               = models.BooleanField(_(u'Verifier'), editable=False)
    licence_manquante      = models.BooleanField(_(u'Licence manquante'), editable=False)
    certificat_manquant    = models.BooleanField(_(u'Certificat manquant'), editable=False)
    autorisation_manquante = models.BooleanField(_(u'Autorisation manquante'), editable=False)
    valide                 = models.BooleanField(_(u'Valide'), editable=False)
    erreur                 = models.BooleanField(_(u'Erreur'), editable=False)
    homme                  = models.BooleanField(_(u'Homme'), editable=False)
    
    def age(self, today=None):
        if not today:
            today = self.equipe.course.date
        try: 
            birthday = self.date_de_naissance.replace(year=today.year)
        except ValueError: # raised when birth date is February 29 and the current year is not a leap year
            birthday = self.date_de_naissance.replace(year=today.year, day=self.date_de_naissance.day-1)
        return today.year - self.date_de_naissance.year - (birthday > today)

    def __str__(self):
        return u'%d%d %s %s' % (self.equipe.numero, self.numero, self.nom, self.prenom)

    def save(self, *args, **kwargs):
        if self.id:
            original = Equipier.objects.get(id=self.id)
            if (original.nom != self.nom or 
                original.prenom != self.prenom or
                original.piece_jointe != self.piece_jointe):
                self.piece_jointe_valide = None
            if (original.nom != self.nom or 
                original.prenom != self.prenom or
                original.autorisation != self.autorisation):
                self.autorisation_valide = None
        piece_jointe_manquante = (
                (not self.piece_jointe and self.piece_jointe_valide != True) or 
                (bool(self.piece_jointe) and self.piece_jointe_valide == False)
            )
        autorisation_manquante = (
                (not self.autorisation and self.autorisation_valide != True) or
                (bool(self.autorisation) and self.autorisation_valide == False)
            )
        self.licence_manquante = self.justificatif == 'licence' and piece_jointe_manquante
        self.certificat_manquant = self.justificatif == 'certificat' and piece_jointe_manquante
        self.autorisation_manquante = self.age() < 18 and autorisation_manquante
        self.verifier = ((bool(self.piece_jointe) and self.piece_jointe_valide == None) or
                         (self.age() < 18 and bool(self.autorisation) and self.autorisation_valide == None))
        self.erreur = self.piece_jointe_valide == False or (self.age() < 18 and self.autorisation_valide == False)
        self.valide = self.piece_jointe_valide == True and (self.age() >= 18 or self.autorisation_valide == True)
        self.homme = self.sexe == 'H'

        if not self.ville2:
            self.ville2 = lookup_ville(self.ville, self.code_postal, self.pays)
        super(Equipier, self).save(*args, **kwargs)

    def dossard(self):
        return self.equipe.numero * 10 + self.numero

    def send_mail(self, nom):
        self.course.send_mail(nom, [self])

class ExtraQuestion(models.Model):
    PAGE_CHOICES = (
        ('Equipe', _(u"Gerant d'équipe")),
        ('Equipier', _(u'Equipier')),
        ('Categorie', _(u'Page finale')),
    )
    TYPE_CHOICES = (
        ('text', _('Texte')),
        ('radio', _('Liste')),
        ('list', _('Liste déroulante')),
        ('checkbox', _('Case à cocher')),
    )
    course = models.ForeignKey(Course, related_name='extra', on_delete=models.CASCADE)
    page = models.CharField(_('Rattaché à'), max_length=20, choices=PAGE_CHOICES)
    type = models.CharField(max_length=200, choices=TYPE_CHOICES)
    label = models.CharField(max_length=200)
    help_text = models.TextField(_('Texte d\'aide'), blank=True, default='')
    price1 = models.DecimalField(_(u"Prix normal"), max_digits=7, decimal_places=2, blank=True, null=True)
    price2 = models.DecimalField(_(u"Prix augmenté"), max_digits=7, decimal_places=2, blank=True, null=True)
    required = models.BooleanField()

    def price(self, d=None):
        if isinstance(d, datetime):
            d = d.date()
        d = d or date.today()
        price = self.price1 or 0
        if self.course.date_augmentation and self.course.date_augmentation <= d:
            price = self.price2 or 0
        return price

    def getPriceByValue(self, d, value):
        if self.type == 'text':
            return None
        if self.type == 'checkbox' and self.price(d):
            return self.price(d) if value else None
        if not hasattr(self, '_choices_prices'):
            self._choice_prices = { x.label: x.price(d) for x in self.choices.all() }
        return self._choice_prices.get(value, None)


    def getField(self):
        choices = map(lambda x: (str(x), x.text()), self.choices.order_by('order'))
        if self.type == 'text':
            field = forms.CharField(label=self.label, required=self.required, help_text=self.help_text)
        if self.type == 'radio':
            field = forms.ChoiceField(label=self.label, required=self.required, help_text=self.help_text, choices=choices, widget=forms.RadioSelect())
        if self.type == 'list':
            field = forms.ChoiceField(label=self.label, required=self.required, help_text=self.help_text, choices=choices)
        if self.type == 'checkbox':
            label = self.label
            price = self.price()
            if price:
                label = '%s (%s€)' % (self.label, price)
            field = forms.BooleanField(label=label, required=self.required, help_text=self.help_text)
        return {
            self.getId(): field,
        }

    def getId(self):
        return 'extra%d' % self.id

class ExtraQuestionChoice(models.Model):
    question = models.ForeignKey(ExtraQuestion, related_name='choices', on_delete=models.CASCADE)
    label = models.CharField(_('Label'), max_length=200)
    price1 = models.DecimalField(_(u"Prix normal"), max_digits=7, decimal_places=2, blank=True, null=True)
    price2 = models.DecimalField(_(u"Prix augmenté"), max_digits=7, decimal_places=2, blank=True, null=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.label

    def price(self, d=None):
        if isinstance(d, datetime):
            d = d.date()
        d = d or date.today()
        price = self.price1 or 0
        if self.question.course.date_augmentation and self.question.course.date_augmentation <= d:
            price = self.price2 or 0
        return price

    def text(self):
        price = self.price()
        if price:
            return '%s (%s€)' % (self.label, price)
        return self.label
    

class Accreditation(models.Model):
    user = models.ForeignKey(User, related_name='accreditations', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name='accreditations', on_delete=models.CASCADE)
    role = models.CharField(_("Role"), max_length=20, choices=ROLE_CHOICES, default='', blank=True)
    class Meta:
        unique_together = (('user', 'course'), )

    def save(self, *args, **kwargs):
        if self.role and self.id  and not Accreditation.objects.get(id=self.id).role:
            send_mail(
                subject='[%s] Accès autorisé' % self.course.uid,
                body="""Votre demande d'accès à la course %s est acceptée.
Connectez vous sur enduroller pour y accéder.
""" % self.course.nom,
                to=[self.user.email],
                reply_to=[self.course.email_contact,],
                content_type='text',
            )
        super().save(*args, **kwargs)

class TemplateMail(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    nom = models.CharField(_('Nom'), max_length=200)
    destinataire = models.CharField(_('Destinataire'), max_length=20, choices=DESTINATAIRE_CHOICES)
    bcc = models.CharField(_(u'Copie cachée à'), max_length=1000, blank=True)
    sujet = models.CharField(_('Sujet'), max_length=200)
    message = models.TextField(_('Message'))
    class Meta:
        unique_together= ( ('course', 'nom'), )

    def __str__(self):
        return self.nom

    def send(self, instances):
        mails = []
        if isinstance(instances, list):
            prefetch_related_objects(instances, 'equipier_set')
        elif hasattr(instances, 'prefetch_related'):
            instances.prefetch_related('equipier_set')
        for instance in instances:
            dests = set()
            if self.destinataire in ('Organisateur', 'Tous'):
                dests.add(self.course.email_contact)
            if self.destinataire in ('Equipe', 'Tous') and isinstance(instance, Equipe):
                    dests.add(instance.gerant_email)
            if self.destinataire in ('Equipiers', 'Tous'):
                if isinstance(instance, Equipier):
                    dests.add(instance.email)
                if isinstance(instance, Equipe):
                    for equipier in instance.equipier_set.filter(numero__lte=F('equipe__nombre')):
                        dests.add(equipier.email)
            
            context = Context({
                "instance": instance,
                'ROOT_URL': 'https://%s' % Site.objects.get_current(),
            })
            subject = Template(self.sujet).render(context)
            message = Template(self.message).render(context)

            bcc = []
            if self.bcc:
                bcc = re.split('[,; ]+', self.bcc)
            m = Mail(
                course=self.course,
                template=self,
                equipe=instance if isinstance(instance, Equipe) else None,
                emetteur=self.course.email_contact,
                destinataires=list(dests),
                bcc=bcc,
                sujet=subject,
                message=message,
            )
            m.save()
            m.send()

class Mail(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    template = models.ForeignKey(TemplateMail, null=True, on_delete=models.SET_NULL)
    equipe = models.ForeignKey(Equipe, null=True, on_delete=models.SET_NULL)
    emetteur = models.EmailField()
    destinataires = ArrayField(models.EmailField())
    bcc = ArrayField(models.EmailField(), blank=True)
    sujet = models.CharField(max_length=200)
    message = models.TextField()
    date = models.DateTimeField(auto_now=True)
    uid = models.CharField(max_length=200)
    error = models.TextField(_('Erreur d\'envoi'), max_length=200, null=True, blank=True)
    read = models.DateTimeField(_('Lu le'), null=True, default=None)

    def send(self):
        if not self.uid:
            self.uid = '%s@%s' % (uuid.uuid4().hex, Site.objects.get_current())
            self.save()
        for dest in self.destinataires:
            send_mail(
                subject=self.sujet,
                body=self.message,
                name=self.course.nom,
                to=[dest],
                bcc=self.bcc,
                reply_to=[self.emetteur,],
                message_id=self.uid,
            )

CHALLENGE_LEVENSHTEIN_DISTANCE = 3
# test:
# from inscriptions.models import *; Challenge.objects.all().delete(); c=Challenge(nom='Challenge Grand Nord 2016'); c.save(); [c.add_course(course) for course in Course.objects.filter(date__year=2016)]
class Challenge(models.Model):
    MODE_CHOICES = (
        ('nord2017', _('Points / Participations (égalités possibles)')),
        ('nord2018', _('Points / Participations / Distance')),
    )

    nom = models.CharField(max_length=200)
    uid = models.CharField(_(u'uid'), max_length=200, validators=[RegexValidator(regex="^[a-z0-9]{3,}$", message=_("Ne doit contenir que des lettres ou des chiffres"))], unique=True)
    logo = models.ImageField(_('Logo'), upload_to='logo', null=True, blank=True)
    courses = models.ManyToManyField(Course, blank=True, related_name='challenges')
    active = models.BooleanField(_(u'Activée'), default=False)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    def add_course(self, course, course_categories=None):
        if course in self.courses.all():
            course_categories = course_categories or { c: c.categories.filter(course=course) for c in self.categories.all() }
            self.del_course(course)
        else:
            course_categories = course_categories or { c: [c] for c in course.categories.all() }
        for c in self.categories.all():
            if c in course_categories:
                c.categories.add(*course_categories[c])
        prefetch_related_objects([self], 'categories')
        prefetch_related_objects([self], 'categories__categories')
        print(self.categories.all()[0].categories.filter(course=course))
        equipes_skiped = [ equipe for equipe in course.equipe_set.select_related('categorie').prefetch_related(Prefetch('equipier_set', Equipier.objects.filter(numero__lte=F('equipe__nombre')))) if not self.inscription_equipe(equipe) ]
        self.compute_course(course)
        return equipes_skiped

    def del_course(self, course):
        course_categories = course.categories.all();
        for c in self.categories.all():
            c.categories.remove(*course_categories)
        EquipeChallenge.objects.filter(equipe__course=course, participation__challenge=self).delete()
        self.participations.annotate(c=Count('equipes')).filter(c=0).delete()


    def compute_course(self, course):
        points = [None, 15, 12, 10, 8, 6, 5, 4, 3, 2, ]
        equipes = EquipeChallenge.objects.filter(
                participation__challenge=self,
                equipe__course=course,
                equipe__position_generale__isnull=False
            ).order_by('equipe__position_generale').prefetch_related('participation__categorie')
        positions = defaultdict(lambda: 1)
        for equipe in equipes:
            pos = positions[equipe.participation.categorie]
            equipe.position = pos
            equipe.points = points[pos] if pos < len(points) else 1
            equipe.save()
            positions[equipe.participation.categorie] += 1

    def compute_challenge(self):
        cats = defaultdict(lambda: 0)
        if self.mode == 'nord2017': 
            courses_points = [ ('position_%s' % c.uid, Sum(Case(When(equipes__equipe__course=c, then='equipes__equipe__position_generale'), default=Value(0), output_field=models.IntegerField()))) for c in self.courses.order_by('date') ]
            previous_position = defaultdict(lambda: None)
            for p in self.participations.select_related('categorie').annotate(p=Sum('equipes__points'), c=Count('equipes'), **dict(courses_points)).order_by('-p', '-c', *[k for k, v in courses_points]):
                if p.c == 0:
                    continue
                pp = previous_position[p.categorie.code]
                print(p.categorie.code, p.equipes.all()[0].equipe.nom, p.position)
                if not pp or pp.p != p.p or pp.c != p.c:
                    cats[p.categorie.code] += 1
                else: # equality
                    if [k for k, v in courses_points if getattr(p, k) and getattr(pp, k)]:
                        print ('course commune');
                        cats[p.categorie.code] += 1

                previous_position[p.categorie.code] = p
                p.position = cats[p.categorie.code]
                p.save()
        elif self.mode == 'nord2018':
            for p in self.participations.select_related('categorie').annotate(p=Sum('equipes__points'), c=Count('equipes'), d=Sum(F('equipes__equipe__course__distance') * F('equipes__equipe__tours'), output_field=models.DecimalField())).order_by('-p', '-c', '-d'):
                if p.c == 0 or p.p == 0:
                    p.position = None
                    p.save()
                    continue
                cats[p.categorie.code] += 1
                p.position = cats[p.categorie.code]
                p.save()


    def inscription_equipe(self, equipe):
        for old_participation in self.participations.filter(equipes__equipe=equipe):
            old_participation.del_equipe(equipe)

        if not any(c for c in self.categories.prefetch_related('categories') if c.valide(equipe)):
            return None

        participations = list(self.find_participation_for_equipe(equipe).prefetch_related('challenge__categories', 'challenge__categories__categories')[:2])
        if participations:
            if len(participations) > 1:
                logger.warning('found multiple participation to challenge %s %s' % (equipe, self))
            participations[0].add_equipe(equipe=equipe)
            return participations[0]
        p = ParticipationChallenge(challenge=self)
        p.save()
        p.add_equipe(equipe=equipe)
        return p

    def find_categories(self, equipiers, categories, course):
        result = {}
        for cc in self.categories.all():
            for ec in categories:
                if not cc.valide_categorie(ec):
                    continue
                if cc.valide_equipiers(equipiers, course):
                    result[ec] = cc
                    break
        return result

    def find_participation_for_equipe(self, equipe):
        equipiers = list(equipe.equipier_set.all())
        return self.find_participation_for_equipe_raw(equipe.course, equipe.nom, equipiers, equipe.categorie)

    def find_participation_for_equipe_raw(self, course, equipe_nom, equipiers_data, categorie):
        if len(equipiers_data) == 0:
            return self.participations.none()

        participation_qs = self.participations.annotate(
            d=CompareNames('nom', Value(equipe_nom)),
        ).filter(
            Q(categorie__isnull=True) | Q(categorie__in=categorie.challenge_categories.filter(challenge=self)),
            d__lt=CHALLENGE_LEVENSHTEIN_DISTANCE,
        )
        
        annotate = {}
        annotate.update({
            'equipiers__nom%s' % e.numero: CompareNames('equipiers__nom', Value(e.nom))
            for e in equipiers_data
        })
        annotate.update({
            'equipiers__prenom%s' % e.numero: CompareNames('equipiers__prenom', Value(e.prenom))
            for e in equipiers_data
        })
        def match_equipier_filter(equipier):
            filtre = Q(**{
                'equipiers__nom%s__lt' % equipier.numero: CHALLENGE_LEVENSHTEIN_DISTANCE,
                'equipiers__prenom%s__lt' % equipier.numero: CHALLENGE_LEVENSHTEIN_DISTANCE,
            })
            if equipier.justificatif == 'licence':
                return Q(equipiers__num_licence=equipier.num_licence) | filtre
            return filtre

        filters = [ match_equipier_filter(e) for e in equipiers_data ]
        equipiers_qs = ParticipationEquipier.objects.filter(
            participation__in=participation_qs
        ).annotate(
            c=Count('equipiers'),
            **annotate,
        ).filter(
            Q(c__gt=0) &
            _or(*filters),
        ).values('participation__id').annotate(c=Count('id')).filter(c__gte=len(equipiers_data) / 2)
        return self.participations.filter(id__in=[ e['participation__id'] for e in equipiers_qs ])

    def test_participation(self):
        count=0
        ko=0
        dup=0
        for course in self.courses.all():
            for e in course.equipe_set.all():
                count+=1
                ps = list(self.find_participation_for_equipe(e))
                if len(ps) > 1:
                    dup+=1
                good_p=None
                for p in ps:
                    if p in [cp.participation for cp in e.challenges.select_related('participation')]:
                        good_p=p
                if e.challenges.get().participation.equipes.count() > 1:
                    if not good_p or len(ps) > 1:
                        ko+=1
                        print(course, len(ps), e.id, e, e.challenges.values('participation'), ps)

        print (count, ko, dup)

    def __str__(self):
        return self.nom

class ChallengeCategorie(models.Model):
    challenge       = models.ForeignKey(Challenge, related_name='categories', on_delete=models.CASCADE)
    nom             = models.CharField(_(u'Nom'), max_length=200)
    code            = models.CharField(_(u'Code'), max_length=200)
    min_equipiers   = models.IntegerField(_(u"Nombre minimum d'équipiers"))
    max_equipiers   = models.IntegerField(_(u"Nombre maximum d'équipiers"))
    min_age         = models.IntegerField(_(u'Age minimum'), default=12)
    sexe            = models.CharField(_(u'Sexe'), max_length=2, choices=MIXITE_CHOICES, blank=True)
    validation      = models.TextField(_(u'Validation function (javascript)'))
    categories      = models.ManyToManyField(Categorie, related_name='challenge_categories')

    def __str__(self):
        return self.code

    def valide(self, equipe):
        if not self.valide_categorie(equipe.categorie):
            return False

        return self.valide_equipiers(list(equipe.equipier_set.all()))

    def valide_categorie(self, categorie):
        return categorie in self.categories.all()

    def valide_equipiers(self, equipiers, course=None):
        if not equipiers:
            return True

        if len(equipiers) < self.min_equipiers or len(equipiers) > self.max_equipiers:
            return False
        for e in equipiers:
            if e.age(course and course.date) < self.min_age:
                return False
        sexes = [e.sexe for e in equipiers]
        if self.sexe == 'H' and 'F' in sexes:
            return False
        if self.sexe == 'F' and 'H' in sexes:
            return False
        if self.sexe == 'HX' and 'H' not in sexes:
            return False
        if self.sexe == 'FX' and 'F' not in sexes:
            return False
        if self.sexe == 'X' and ('H' not in sexes or 'F' not in sexes):
            return False
        #TODO self.validation
        return True

class ParticipationChallenge(models.Model):
    challenge = models.ForeignKey(Challenge, related_name='participations', on_delete=models.CASCADE)
    categorie = models.ForeignKey(ChallengeCategorie, related_name='participations', default=None, null=True, blank=True, on_delete=models.SET_NULL)
    position = models.IntegerField(null=True, blank=True)
    nom = models.CharField(_(u"Nom d'équipe"), max_length=30)

    def equipes_dict(self):
        return { e.equipe.course.uid: e for e in self.equipes.all() }

    def add_equipe(self, equipe, points=0):
        EquipeChallenge.objects.filter(participation__challenge=self.challenge, equipe=equipe).delete()
        e = self.equipes.create(
            participation=self,
            equipe=equipe,
            points=points,
        )
        modified = False
        if not self.nom:
            self.nom = equipe.nom
            modified = True
        if not self.categorie:
            for c in self.challenge.categories.all():
                if c.valide(equipe):
                    self.categorie = c
                    modified = True
                    break
        if modified:
            self.save()

        pequipiers = list(self.equipiers.all())
        annotate = {}
        annotate.update({
            'nom%s' % e.id: CompareNames('nom', Value(e.nom))
            for e in pequipiers
        })
        annotate.update({
            'prenom%s' % e.id: CompareNames('prenom', Value(e.prenom))
            for e in pequipiers
        })
        count = 0
        for equipier in equipe.equipier_set.annotate(**annotate):
            matched_pequipier = None
            for pequipier in pequipiers:
                if equipier.num_licence == pequipier.num_licence or (
                    getattr(equipier, 'nom%s' % pequipier.id) < CHALLENGE_LEVENSHTEIN_DISTANCE and 
                    getattr(equipier, 'prenom%s' % pequipier.id) < CHALLENGE_LEVENSHTEIN_DISTANCE):
                    matched_pequipier = pequipier
                    break
            if not matched_pequipier:
                count += 1
                matched_pequipier = ParticipationEquipier(
                    nom=equipier.nom,
                    prenom=equipier.prenom,
                    sexe=equipier.sexe,
                    num_licence=equipier.num_licence,
                    participation=self,
                )
                matched_pequipier.save()
            if not matched_pequipier.num_licence and equipier.num_licence:
                matched_pequipier.num_licence = equipier.num_licence
                matched_pequipier.save()
            matched_pequipier.equipiers.add(equipier)
        logger.info('add equipe %s to participation %s, %s not matched' % (equipe, self, count))
        return e

    def del_equipe(self, equipe):
        for equipier in equipe.equipier_set.all():
            for e in self.equipiers.all():
                e.equipiers.remove(equipier)   
        self.equipiers.annotate(c=Count('equipiers')).filter(c=0).delete()
        self.equipes.filter(equipe=equipe).delete()
        if self.equipes.count() == 0:
            self.delete()

    def __str__(self):
        return 'Participation %s %s' % (self.challenge, self.nom)
        

class EquipeChallenge(models.Model):
    equipe = models.ForeignKey(Equipe, related_name='challenges', on_delete=models.CASCADE)
    participation = models.ForeignKey(ParticipationChallenge, related_name='equipes', on_delete=models.CASCADE)
    points = models.IntegerField()

    class Meta:
        unique_together = (('equipe', 'participation'), )

    def __str__(self):
        return 'Participation %s - %s' % (self.participation, self.equipe)

class ParticipationEquipier(models.Model):
    participation = models.ForeignKey(ParticipationChallenge, related_name='equipiers', on_delete=models.CASCADE)
    nom           = models.CharField(_(u'Nom'), max_length=200)
    prenom        = models.CharField(_(u'Prénom'), max_length=200, blank=True)
    sexe          = models.CharField(_(u'Sexe'), max_length=1, choices=SEXE_CHOICES)
    num_licence   = models.CharField(_(u'Numéro de licence'), max_length=15, blank=True)
    equipiers     = models.ManyToManyField(Equipier, related_name='particpations')

    def courses(self):
        return [ e.equipe.course for e in self.equipiers.all() ]

    def __str__(self):
        return 'ParticipationEquipier %s - %s %s' % (self.participation, self.nom, self.prenom)

def _or(*conds):
    conds = list(conds)
    res = conds.pop(0)
    while conds:
        res = res | conds.pop(0)
    return res

class Levenshtein(Func):
    function = 'levenshtein'
class Unaccent(Func):
    function = 'unaccent'
class RegexpReplace(Func):
    function = 'regexp_replace'
class CompareNames(Func):
    function = 'levenshtein'
    def __init__(self, a, b):
        self.a = a
        self.b = b
        super().__init__(
            Unaccent(Lower(RegexpReplace(a, Value('[ -]\\+'), Value(' ')))),
            Unaccent(Lower(RegexpReplace(b, Value('[ -]\\+'), Value(' '))))
        )
    def get_group_by_cols(self):
        cols = []
        for source in self._parse_expressions([self.a, self.b]):
            cols.extend(source.get_group_by_cols())
        return cols

class LiveSnapshot(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date = models.DateTimeField()
    received = models.DateTimeField(auto_now=True)

class LiveResult(models.Model):
    snapshot = models.ForeignKey(LiveSnapshot, on_delete=models.CASCADE)
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE)
    position = models.IntegerField()
    tours = models.IntegerField()
    temps = models.DecimalField(max_digits=8, decimal_places=3)
    meilleur_tour = models.DecimalField(max_digits=8, decimal_places=3)
    penalité = models.IntegerField()

class Paiement(models.Model):
    TYPE_CHOICES = (
        ('espèce', _('espèce')),
        ('chèque', _('chèque')),
        ('paypal', _('paypal')),
        ('stripe', _('stripe')),
        ('virement', _('virement')),
        ('autre', _('autre')),
    )
    MANUAL_TYPE_CHOICES = (
        ('espèce', _('espèce')),
        ('chèque', _('chèque')),
        ('virement', _('virement')),
        ('autre', _('autre')),
    )
    date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=200, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    montant_frais = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    detail = models.TextField(blank=True)
    stripe_intent = models.CharField(max_length=200, blank=True, null=True)

    def send_equipes_mail(self):
        if self.montant:
            try:
                equipes = Equipe.objects.filter(paiements__paiement=self)
                courses = Course.objects.filter(equipe__in=equipes).distinct()
                for course in courses:
                    mail = TemplateMail.objects.select_related('course').get(course=course, nom='paiement')
                    mail.send(equipes.filter(course=course))
            except Exception as e:
                traceback.print_exc()

    def send_admin_mail(self):
        subject = 'Paiement reçu %s' % (', '.join(str(e.equipe) for e in self.equipes.all()), )
        message = render_to_string('mails/paiement_admin.html', {
            'paiement': self,
        })
        dest = [ c.email_contact for c in Course.objects.filter(equipe__paiements__paiement=self) ]
        send_mail(
            subject=subject,
            body=message,
            to=dest,
        )


class PaiementRepartition(models.Model):
    paiement = models.ForeignKey(Paiement, related_name='equipes', on_delete=models.CASCADE)
    equipe = models.ForeignKey(Equipe, related_name='paiements', on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    montant_frais = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    def paye(self):
        paiements = self.equipe.paiements.all()
        if self.id:
            paiements = paiements.exclude(id=self.id)
        return paiements.aggregate(m=Sum('montant'))['m'] or Decimal('0.00')

    def reste(self):
        return self.equipe.prix - self.paye()
