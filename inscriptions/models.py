# -*- coding: utf-8 -*-
from collections import defaultdict
from operator import itemgetter
from django.utils.translation import ugettext_lazy as _
from django_countries.fields import CountryField
from django.conf import settings
from django.template.loader import render_to_string
from django.core.validators import RegexValidator
from django.template import Template, Context
from django.core.mail import EmailMessage
import os, re, requests, json, sys
from django.db import models, transaction
from django.db.models.query import prefetch_related_objects
from datetime import date, timedelta
from decimal import Decimal
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Value, F, When, Case
from django.db.models.functions import Coalesce
from django.contrib.sites.models import Site
from .utils import iriToUri, MailThread, ChallengeInscriptionEquipe
from Levenshtein import distance
import logging
import traceback
import pytz

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

CONNU_CHOICES = (
    (u'Site Roller en Ligne.com', _(u'Site Roller en Ligne.com')),
    (u'Facebook', _('Facebook')),
    (u'Presse', _(u'Presse')),
    (u'Bouche à oreille', _(u'Bouche à oreille')),
    (u'Flyer pendant une course', _(u'Flyer pendant une course')),
    (u'Flyer pendant une randonnée', _(u'Flyer pendant une randonnée')),
    (u'Affiche', _(u'Affiche')),
    (u'Informations de la Mairie', _(u'Information de la Mairie')),
    (u'Par mon club', _(u'Par mon club')),
    (u'Autre', _(u'Autre')),
)

TAILLES_CHOICES = (
    ('XS', _('XS')),
    ('S', _('S')),
    ('M', _('M')),
    ('L', _('L')),
    ('XL', _('XL')),
    ('XXL', _('XXL')),
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

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = self.nom.lower().replace(' ', '_')
        if not self.id:
            message = EmailMessage('Nouvelle course %s' % self.nom, """%s.
""" % self.nom, settings.DEFAULT_FROM_EMAIL, [ settings.SERVER_EMAIL ])
            MailThread([message]).start()
        if self.active and self.id  and not Course.objects.get(id=self.id).active:
            message = EmailMessage('Votre course %s est activée' % self.nom, """Votre course %s est activée.
Les inscriptions pourront commencer à la date que vous avez choisi.
""" % self.nom, settings.DEFAULT_FROM_EMAIL, [ self.email_contact ])
            MailThread([message]).start()
        super(Course, self).save(*args, **kwargs)

    def __str__(self):
        return '%s (%s)' % (self.nom, self.date)

    def send_mail(self, nom, instances):
        mail = TemplateMail.objects.get(course=self, nom=nom)
        mail.send(instances)

    @property
    def date_certificat(self):
        return self.date - timedelta(days=365)

    def stats(self):
        model_stats = {
            "equipes": 0,
            "equipiers": 0,
            "hommes": 0,
            "femmes": 0,
            "paiement": 0,
            "paiement_paypal": 0,
            "prix": 0,
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
            "connu": {},
            "clubs": {},
        }

        equipes = (Equipe.objects.filter(course=self)
            .annotate(
                equipiers_count=Count('equipier'),
                verifier_count=Coalesce(Sum('equipier__verifier'), Value(0)),
                licence_manquantes_count=Coalesce(Sum('equipier__licence_manquante'), Value(0)),
                certificat_manquants_count=Coalesce(Sum('equipier__certificat_manquant'), Value(0)),
                autorisation_manquantes_count=Coalesce(Sum('equipier__autorisation_manquante'), Value(0)),
                valide_count=Coalesce(Sum('equipier__valide'), Value(0)),
                erreur_count=Coalesce(Sum('equipier__erreur'), Value(0)),
                hommes_count=Coalesce(Sum('equipier__homme'), Value(0)),
            ).select_related('categorie', 'gerant_ville2')
            .prefetch_related('equipier_set')
            .prefetch_related('equipier_set__equipe')
            .prefetch_related('equipier_set__equipe__course')
        )
        tz = pytz.timezone('Europe/Paris')
        for equipe in equipes:
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

            stats['paiement'] = float(equipe.paiement or 0)
            stats['prix'] = float(equipe.prix)
            stats['nbcertifenattente'] = equipe.licence_manquantes_count + equipe.certificat_manquants_count + equipe.autorisation_manquantes_count
            stats[equipe.categorie.code] += 1;
            if equipe.paiement_paypal():
                stats['paiement_paypal'] += 1


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
            if equipe.connu not in result['connu']:
                result['connu'][equipe.connu] = 0;
            result['connu'][equipe.connu] += 1;

        result['connu'] = list(result['connu'].items())
        sorted(result['connu'], key=itemgetter(1), reverse=True)

        result['villes'] = [
            {
                'nom': ville.nom,
                'pays': ville.pays,
                'lat': float(ville.lat),
                'lng': float(ville.lng),
                'count': ville.count,
            } for ville in Ville.objects.filter(equipier__equipe__course=self).annotate(count=Count('equipier'))
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

class Categorie(models.Model):
    course          = models.ForeignKey(Course, related_name='categories')
    nom             = models.CharField(_(u'Nom'), max_length=200)
    code            = models.CharField(_(u'Code'), max_length=10)
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
    gerant_pays        = CountryField(_(u'Pays'), default='FR')
    gerant_email       = models.EmailField(_(u'e-mail'), max_length=200)
    password           = models.CharField(_(u'Mot de passe'), max_length=200, blank=True)
    gerant_telephone   = models.CharField(_(u'Téléphone'), max_length=200, blank=True)
    categorie          = models.ForeignKey(Categorie)
    course             = models.ForeignKey(Course)
    nombre             = models.IntegerField(_(u"Nombre d'équipiers"))
    paiement_info      = models.CharField(_(u'Détails'), max_length=200, blank=True)
    prix               = models.DecimalField(_(u'Prix'), max_digits=5, decimal_places=2)
    paiement           = models.DecimalField(_(u'Paiement reçu'), max_digits=5, decimal_places=2, null=True, blank=True)
    dossier_complet    = models.NullBooleanField(_(u'Dossier complet'))
    date               = models.DateTimeField(_(u"Date d'insciption"), auto_now_add=True)
    commentaires       = models.TextField(_(u'Commentaires'), blank=True)
    gerant_ville2      = models.ForeignKey(Ville, null=True)
    numero             = models.IntegerField(_(u'Numéro'))
    connu              = models.CharField(_('Comment avez vous connu la course ?'), max_length=200, choices=CONNU_CHOICES)
    date_facture       = models.DateField(_('Date facture'), blank=True, null=True)
    tours              = models.IntegerField(_('Nombre de tours'), blank=True, null=True)
    temps              = models.DecimalField(_('Temps (en secondes)'), max_digits=9, decimal_places=3, null=True, blank=True)
    position_generale  = models.IntegerField(_('Position générale'), blank=True, null=True)
    position_categorie = models.IntegerField(_('Position catégorie'), blank=True, null=True)

    class Meta:
        unique_together = ( ('course', 'numero'), )

    def __str__(self):
        return u'%s - %s - %s - %s' % (self.numero, self.course.uid, self.categorie, self.nom)

    def licence_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.licence_manquante]

    def certificat_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.certificat_manquant]

    def autorisation_manquantes(self):
        return [equipier for equipier in self.equipier_set.all() if equipier.autorisation_manquante]

    def verifier(self):
        if hasattr(self, 'verifier_count'):
            return self.verifier_count > 0
        return len([equipier for equipier in self.equipier_set.all() if equipier.verifier]) > 0

    def paiement_complet(self):
        return (self.paiement or Decimal(0)) >= self.prix
    
    def dossier_complet_auto(self):
        if hasattr(self, 'erreur_count'):
            if self.erreur_count > 0:
                return False
        elif len([equipier for equipier in self.equipier_set.all() if equipier.erreur]) > 0:
            return False
        if hasattr(self, 'valide_count'):
            if self.valide_count < self.nombre:
                return None
        elif len([equipier for equipier in self.equipier_set.all() if not equipier.valide]) > 0:
            return None
        return True

    def frais_paypal(self):
        if self.course.frais_paypal_inclus:
            return Decimal('0.00')
        return ( self.prix + Decimal('0.25') ) / ( Decimal('1.000') - Decimal('0.034') ) - self.prix

    def prix_paypal(self):
        return self.prix + self.frais_paypal()

    def paiement_paypal(self):
        return self.paiement_info.startswith('Paypal ') # and self.prix_paypal() - Decimal('0.01') < self.paiement and self.paiement < self.prix_paypal() + Decimal('0.01')
        
    def save(self, *args, **kwargs):
        if self.id:
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

            paiement = Equipe.objects.get(id=self.id).paiement
            if paiement != self.paiement:
                try:
                    self.send_mail('paiement')
                except Exception as e:
                    traceback.print_exc()
                try:
                    self.send_mail('paiement_admin')
                except Exception as e:
                    traceback.print_exc()
        else:
            if not self.numero:
                self.numero = self.getNumero()

        if not self.gerant_ville2_id:
            self.gerant_ville2 = lookup_ville(self.gerant_ville, self.gerant_code_postal, self.gerant_pays)
        super(Equipe, self).save(*args, **kwargs)

        ChallengeInscriptionEquipe(self).start()


    def send_mail(self, nom):
        self.course.send_mail(nom, [self])

    def getNumero(self):
        start = self.categorie.numero_debut
        end = self.categorie.numero_fin

        res = Equipe.objects.raw("""SELECT e1.id as id, e1.numero as numero FROM inscriptions_equipe e1 
                LEFT JOIN inscriptions_equipe e2 ON e1.numero=e2.numero-1 AND e1.course_id=e2.course_id
                WHERE e1.course_id=%s AND e1.numero>=%s AND e1.numero<=%s AND e2.numero IS NULL LIMIT 1""", 
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
        return self.date + timedelta(days=31)

    def temps_humain(self):
        if not self.temps:
            return ''
        s = []
        t = self.temps
        while t:
            f = ('%06' if not s else '%02') if t > 60 else '%'
            f += 'd' if s else '.3f'
            s.append(f % (t % 60))
            t = (t / 60).to_integral()
        s.reverse()
        return ':'.join(s)

class Equipier(models.Model):
    numero            = models.IntegerField(_(u'Numéro'))
    equipe            = models.ForeignKey(Equipe)
    nom               = models.CharField(_(u'Nom'), max_length=200)
    prenom            = models.CharField(_(u'Prénom'), max_length=200, blank=True)
    sexe              = models.CharField(_(u'Sexe'), max_length=1, choices=SEXE_CHOICES)
    adresse1          = models.CharField(_(u'Adresse'), max_length=200, blank=True)
    adresse2          = models.CharField(_(u'Adresse'), max_length=200, blank=True)
    ville             = models.CharField(max_length=200)
    code_postal       = models.CharField(max_length=200)
    pays              = CountryField(_(u'Pays'), default='FR')
    email             = models.EmailField(_(u'e-mail'), max_length=200, blank=True)
    date_de_naissance = models.DateField(_(u'Date de naissance'))
    autorisation      = models.FileField(_(u'Autorisation parentale'), upload_to='certificats', blank=True)
    autorisation_valide  = models.NullBooleanField(_(u'Autorisation parentale valide'))
    justificatif      = models.CharField(_(u'Justificatif'), max_length=15, choices=JUSTIFICATIF_CHOICES)
    num_licence       = models.CharField(_(u'Numéro de licence'), max_length=15, blank=True)
    piece_jointe      = models.FileField(_(u'Certificat ou licence'), upload_to='certificats', blank=True)
    piece_jointe_valide  = models.NullBooleanField(_(u'Certificat ou licence valide'))
    ville2            = models.ForeignKey(Ville, null=True)
    transpondeur      = models.CharField(_(u'Transpondeur'), max_length=20, blank=True)
    taille_tshirt     = models.CharField(_(u'Taille T-shirt'), max_length=3, choices=TAILLES_CHOICES, blank=True)

    # Pre-calculated fields
    verifier               = models.BooleanField(_(u'Verifier'), editable=False)
    licence_manquante      = models.BooleanField(_(u'Licence manquante'), editable=False)
    certificat_manquant    = models.BooleanField(_(u'Certificat manquant'), editable=False)
    autorisation_manquante = models.BooleanField(_(u'Autorisation manquante'), editable=False)
    valide                 = models.BooleanField(_(u'Valide'), editable=False)
    erreur                 = models.BooleanField(_(u'Erreur'), editable=False)
    homme                  = models.BooleanField(_(u'Homme'), editable=False)
    
    def age(self):
        today = self.equipe.course.date
        try: 
            birthday = self.date_de_naissance.replace(year=today.year)
        except ValueError: # raised when birth date is February 29 and the current year is not a leap year
            birthday = self.date_de_naissance.replace(year=today.year, day=self.date_de_naissance.day-1)
        return today.year - self.date_de_naissance.year - (birthday > today)

    def __str__(self):
        return u'%d' % self.numero

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
        self.licence_manquante = self.justificatif == 'licence' and not self.piece_jointe_valide and not self.piece_jointe
        self.certificat_manquant = self.justificatif == 'certificat' and not self.piece_jointe_valide and not self.piece_jointe
        self.autorisation_manquante = self.age() < 18 and not self.autorisation_valide and not self.autorisation
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

class Accreditation(models.Model):
    user = models.ForeignKey(User, related_name='accreditations')
    course = models.ForeignKey(Course, related_name='accreditations')
    role = models.CharField(_("Role"), max_length=20, choices=ROLE_CHOICES, default='', blank=True)
    class Meta:
        unique_together = (('user', 'course'), )

    def save(self, *args, **kwargs):
        if self.role and self.id  and not Accreditation.objects.get(id=self.id).role:
            message = EmailMessage('[%s] Accès autorisé' % self.course.uid, """Votre demande d'accès à la course %s est acceptée.
Connectez vous sur enduroller pour y accéder.
""" % self.course.nom, settings.DEFAULT_FROM_EMAIL, [ self.user.email ], reply_to=[self.course.email_contact,])
            MailThread([message]).start()
        super().save(*args, **kwargs)

class TemplateMail(models.Model):
    course = models.ForeignKey(Course)
    nom = models.CharField(_('Nom'), max_length=200)
    destinataire = models.CharField(_('Destinataire'), max_length=20, choices=DESTINATAIRE_CHOICES)
    bcc = models.CharField(_(u'Copie cachée à'), max_length=1000, blank=True)
    sujet = models.CharField(_('Sujet'), max_length=200)
    message = models.TextField(_('Message'))
    class Meta:
        unique_together= ( ('course', 'nom'), )

    def send(self, instances):
        messages = []
        if isinstance(instances, list):
            prefetch_related_objects(instances, ('equipier_set', ))
        elif hasattr(instances, 'prefetch_related'):
            instances.prefetch_related('equipiers')
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
                    for equipier in instance.equipier_set.all():
                        dests.add(equipier.email)
            
            context = Context({
                "instance": instance,
                'ROOT_URL': 'http://%s' % Site.objects.get_current(),
            })
            subject = Template(self.sujet).render(context)
            message = Template(self.message).render(context)

            bcc = []
            if self.bcc:
                bcc = re.split('[,; ]+', self.bcc)
            for dest in dests:
                message = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [ dest ], bcc, reply_to=[self.course.email_contact,])
                message.content_subtype = "html"
                messages.append(message)
        MailThread(messages).start()

# test:
# from inscriptions.models import *; Challenge.objects.all().delete(); c=Challenge(nom='Challenge Grand Nord 2016'); c.save(); [c.add_course(course) for course in Course.objects.filter(date__year=2016)]
class Challenge(models.Model):
    nom = models.CharField(max_length=200)
    uid = models.CharField(_(u'uid'), max_length=200, validators=[RegexValidator(regex="^[a-z0-9]{3,}$", message=_("Ne doit contenir que des lettres ou des chiffres"))], unique=True)
    logo = models.ImageField(_('Logo'), upload_to='logo', null=True, blank=True)
    courses = models.ManyToManyField(Course, null=True, blank=True, related_name='challenges')
    active = models.BooleanField(_(u'Activée'), default=False)

    def add_course(self, course, course_categories=None):
        with transaction.atomic():
            if course in self.courses.all():
                course_categories = course_categories or { c: c.categories.filter(course=course) for c in self.categories.all() }
                self.del_course(course)
            else:
                course_categories = course_categories or { c: [c] for c in course.categories.all() }
            for c in self.categories.all():
                if c in course_categories:
                    c.categories.add(*course_categories[c])
            print(self.categories.all()[0].categories.filter(course=course))
            equipes_skiped = [ equipe for equipe in course.equipe_set.all() if not self.inscription_equipe(equipe) ]
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
        cats = defaultdict(lambda: 1)
        courses_points = [ ('points_%s' % c.uid, Sum(Case(When(equipes__equipe__course=c, then='equipes__points'), default=Value(0), output_field=models.IntegerField()))) for c in self.courses.order_by('-date') ]
        #for p in self.participations.annotate(p=Sum('equipes__points'), c=Count('equipes'), d=Sum(F('equipes__equipe__course__distance') * F('equipes__equipe__tours') / Coalesce(F('equipes__equipe__temps'), Value(1)))).order_by('-p', 'c', 'd'):
        print(self.participations.annotate(p=Sum('equipes__points'), c=Count('equipes'), **dict(courses_points)).order_by('-p', 'c', *['-' + k for k, v in courses_points]).query.sql_with_params())
        for p in self.participations.annotate(p=Sum('equipes__points'), c=Count('equipes'), **dict(courses_points)).order_by('-p', 'c', *['-' + k for k, v in courses_points]):
            p.position = cats[p.categorie.code]
            p.save()
            cats[p.categorie.code] += 1

    def inscription_equipe(self, equipe):
        ParticipationChallenge.objects.filter(challenge=self, equipes__equipe=equipe).delete()
        if not any(c for c in self.categories.all() if c.valide(equipe)):
            return None

        for p in self.participations.prefetch_related('equipes__equipe'):
            if any(distance(equipe.nom.lower(), e.equipe.nom.lower()) < 3 for e in p.equipes.all()) and p.match(equipe):
                p.add_equipe(equipe=equipe)
                return p
        p = ParticipationChallenge(challenge=self)
        p.save()
        p.add_equipe(equipe=equipe)
        return p

class ChallengeCategorie(models.Model):
    challenge       = models.ForeignKey(Challenge, related_name='categories')
    nom             = models.CharField(_(u'Nom'), max_length=200)
    code            = models.CharField(_(u'Code'), max_length=10)
    min_equipiers   = models.IntegerField(_(u"Nombre minimum d'équipiers"))
    max_equipiers   = models.IntegerField(_(u"Nombre maximum d'équipiers"))
    min_age         = models.IntegerField(_(u'Age minimum'), default=12)
    sexe            = models.CharField(_(u'Sexe'), max_length=2, choices=MIXITE_CHOICES, blank=True)
    validation      = models.TextField(_(u'Validation function (javascript)'))
    categories      = models.ManyToManyField(Categorie, related_name='+')

    def __str__(self):
        return self.code

    def valide(self, equipe):
        if equipe.categorie not in self.categories.all():
            return False

        equipiers = list(equipe.equipier_set.all())
        if not equipiers:
            return True

        if len(equipiers) < self.min_equipiers or len(equipiers) > self.max_equipiers:
            return False
        for e in equipiers:
            if e.age() < self.min_age:
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
    challenge = models.ForeignKey(Challenge, related_name='participations')
    categorie = models.ForeignKey(ChallengeCategorie, related_name='participations', default=None, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)

    def equipes_dict(self):
        return { e.equipe.course.uid: e for e in self.equipes.all() }

    def add_equipe(self, equipe, point=0):
        EquipeChallenge.objects.filter(participation__challenge=self.challenge, equipe=equipe).delete()
        e = EquipeChallenge(
            participation=self,
            equipe=equipe,
            points=0,
        )
        e.save()
        self.equipes.add(e)
        if not self.categorie:
            for c in self.challenge.categories.all():
                if c.valide(equipe):
                    self.categorie = c
                    self.save()
        return e
        
    def match(self, equipe):
        if self.categorie and not self.categorie.valide(equipe):
            return False
        equipiers_challenge = Equipier.objects.filter(equipe__challenges__participation=self)
        c = 0
        equipiers = equipe.equipier_set.all()
        for e in equipiers:
            for e2 in equipiers_challenge:
                if e.justificatif == 'licence' and e2.justificatif == 'licence' and e.num_licence == e2.num_licence:
                    c += 1
                elif distance(e.nom.lower(), e2.nom.lower()) < 3 and distance(e.prenom.lower(), e2.prenom.lower()) < 3:
                    c += 1
        return c >= len(equipiers) / 2


class EquipeChallenge(models.Model):
    equipe = models.ForeignKey(Equipe, related_name='challenges')
    participation = models.ForeignKey(ParticipationChallenge, related_name='equipes')
    points = models.IntegerField()

    class Meta:
        unique_together = (('equipe', 'participation'), )
