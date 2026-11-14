"""Geocodage local des communes a partir du referentiel `CodePostal` (GeoNames).

Aucun appel reseau : voir `docs/stats-repair-plan.md`.
"""
import re
import unicodedata
from collections import Counter, namedtuple
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt

VALEURS_VIDES = {'', '?', '-'}


def normaliser_nom(nom):
    """minuscules, sans accents ni ponctuation, `st` -> `saint`, sans cedex ni arrondissement."""
    nom = unicodedata.normalize('NFKD', nom or '')
    nom = ''.join(c for c in nom if not unicodedata.combining(c)).lower()
    nom = re.sub(r"[-'’,/._()]+", ' ', nom)
    nom = re.sub(r'\bcedex\b.*$', '', nom)
    nom = re.sub(r'\s+', ' ', nom).strip()
    nom = re.sub(r'\s\d{1,2}\s?(er|e|eme|ieme)?$', '', nom)
    nom = re.sub(r'\bst\b', 'saint', nom)
    nom = re.sub(r'\bste\b', 'sainte', nom)
    return nom


def normaliser_cp(cp, pays):
    """Forme normalisee d'un code postal (celle stockee dans `CodePostal`)."""
    cp = (cp or '').strip().upper()
    pays = (pays or '').upper()
    if pays == 'GB':
        if ' ' in cp:
            return cp.split()[0]
        return cp[:-3] if len(cp) > 4 else cp
    cp = re.sub(r'[\s-]+', '', cp) if pays != 'CA' else re.sub(r'\s+', '', cp)
    if pays == 'NL':
        return cp[:4]
    if pays == 'CA':
        return cp[:3]
    # prefixe de pays (F-75000, D-10115, CH-1000...)
    return re.sub(r'^[A-Z]{1,2}(?=\d)', '', cp)


Resultat = namedtuple('Resultat', 'nom pays region lat lng approximatif')

SEUIL_NOM = 0.6
RAYON_HOMONYMES_KM = 25


def nom_affichage(nom):
    """Nom d'une commune pour l'affichage : sans arrondissement (`Paris 15` -> `Paris`)."""
    return re.sub(r'\s+\d{1,2}\s?(er|e|eme|ème|ieme)?$', '', (nom or '').strip(), flags=re.I)


def _distance_km(a, b):
    lat1, lng1, lat2, lng2 = map(radians, (a.lat, a.lng, b.lat, b.lng))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def _resultat(c, approximatif=False):
    return Resultat(c.nom, c.pays, c.region, c.lat, c.lng, approximatif)


def _par_code_postal(candidats, nom_n):
    exacts = [c for c in candidats if c.nom_normalise == nom_n]
    if exacts:
        return exacts[0]
    if len(candidats) == 1:
        return candidats[0]
    meilleur = max(candidats, key=lambda c: SequenceMatcher(None, c.nom_normalise, nom_n).ratio())
    if SequenceMatcher(None, meilleur.nom_normalise, nom_n).ratio() >= SEUIL_NOM:
        return meilleur
    return None  # code postal partage et nom sans rapport : on prefere ne pas deviner


def _plus_proches(communes, nom_n, divisant):
    """Communes au nom le plus proche selon `levenshtein` (PostgreSQL, extension fuzzystrmatch,
    comme `CompareNames` pour les challenges). Distance max : un `divisant`-ieme de la longueur
    du nom. `None` si aucune, ou si des homonymes eloignes se disputent la premiere place."""
    from django.db.models import IntegerField, Value
    from .models import Levenshtein
    maxi = max(1, len(nom_n) // divisant)
    proches = list(communes.annotate(
        d=Levenshtein('nom_normalise', Value(nom_n), output_field=IntegerField()),
    ).filter(d__lte=maxi).order_by('d', 'id')[:20])
    if not proches:
        return None
    ex_aequo = [c for c in proches if c.d == proches[0].d]
    if all(_distance_km(proches[0], c) <= RAYON_HOMONYMES_KM for c in ex_aequo):
        return proches[0]
    return None


def _par_nom_approx(pays, cp, nom_n):
    """Le code postal ne donne rien : nom de ville approchant (fautes de frappe), d'abord dans
    le departement du code postal (FR, plus tolerant), puis dans tout le pays. Approximatif."""
    if len(nom_n) < 3:
        return None
    communes = CodePostalModel().objects.filter(pays=pays)
    if pays == 'FR' and re.fullmatch(r'\d{5}', cp):
        prefixe = cp[:3] if cp[:2] in ('97', '98') else cp[:2]
        commune = _plus_proches(communes.filter(code_postal__startswith=prefixe), nom_n, 3)
        if commune:
            return commune
    return _plus_proches(communes, nom_n, 4)


def _par_nom(pays, nom_n):
    candidats = list(CodePostalModel().objects.filter(pays=pays, nom_normalise=nom_n))
    if not candidats:
        return None
    premier = candidats[0]
    if all(_distance_km(premier, c) <= RAYON_HOMONYMES_KM for c in candidats):
        return premier
    return None  # homonymes eloignes : on prefere ne pas deviner


def _par_departement(pays, cp):
    """FR : barycentre des communes du meme departement (approximatif)."""
    if pays != 'FR' or not re.fullmatch(r'\d{5}', cp):
        return None
    prefixe = cp[:3] if cp[:2] in ('97', '98') else cp[:2]
    communes = list(CodePostalModel().objects.filter(pays='FR', code_postal__startswith=prefixe))
    if not communes:
        return None
    n = len(communes)
    departement, region = Counter((c.departement, c.region) for c in communes).most_common(1)[0][0]
    return Resultat(departement or ('Département ' + prefixe), 'FR', region,
                    round(sum(c.lat for c in communes) / n, 7), round(sum(c.lng for c in communes) / n, 7), True)


def CodePostalModel():
    from .models import CodePostal
    return CodePostal


def trouver(nom, cp, pays):
    """Commune la plus probable pour (nom, code postal, pays), ou `None`.

    Paliers : code postal + nom exact, nom proche, code postal seul, nom seul
    (sans homonyme eloigne), nom approchant (fuzzy), barycentre du departement (FR).
    Voir la spec.
    """
    pays = (pays or '').strip().upper()
    nom = (nom or '').strip()
    cp = (cp or '').strip()
    if not pays or (nom in VALEURS_VIDES and cp in VALEURS_VIDES):
        return None
    nom_n = '' if nom in VALEURS_VIDES else normaliser_nom(nom)
    cp_n = '' if cp in VALEURS_VIDES else normaliser_cp(cp, pays)
    if cp_n:
        candidats = list(CodePostalModel().objects.filter(pays=pays, code_postal=cp_n).order_by('nom_normalise', 'id'))
        commune = _par_code_postal(candidats, nom_n) if candidats else None
        if commune:
            return _resultat(commune)
    if nom_n:
        commune = _par_nom(pays, nom_n)
        if commune:
            return _resultat(commune)
        commune = _par_nom_approx(pays, cp_n, nom_n)
        if commune:
            return _resultat(commune, approximatif=True)
    return _par_departement(pays, cp_n)
