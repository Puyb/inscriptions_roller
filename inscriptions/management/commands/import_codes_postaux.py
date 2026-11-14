"""Importe le referentiel GeoNames des codes postaux dans `CodePostal`.

    ./manage.py import_codes_postaux                  # pays presents dans les equipes (+ FR)
    ./manage.py import_codes_postaux --pays FR,BE     # telecharge FR.zip et BE.zip
    ./manage.py import_codes_postaux --fichier allCountries.zip --pays FR

Idempotent : le contenu des pays importes est remplace. Le telechargement est la
seule operation reseau, uniquement a la demande de l'operateur.
Donnees : GeoNames, CC BY 4.0 (https://www.geonames.org/).
"""
import csv
import io
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inscriptions.geocoding import normaliser_cp, normaliser_nom
from inscriptions.models import CodePostal, Equipe

URL = 'https://download.geonames.org/export/zip/%s.zip'
BATCH = 5000


def lire_lignes(fichier):
    """Itere sur les lignes (listes de colonnes) d'un .txt ou d'un .zip GeoNames."""
    if zipfile.is_zipfile(fichier):
        with zipfile.ZipFile(fichier) as z:
            noms = [n for n in z.namelist() if n.endswith('.txt') and 'readme' not in n.lower()]
            if not noms:
                raise CommandError('Aucun fichier .txt dans %s' % fichier)
            with z.open(noms[0]) as f:
                yield from csv.reader(io.TextIOWrapper(f, encoding='utf-8'), delimiter='\t')
    else:
        with open(fichier, encoding='utf-8', newline='') as f:
            yield from csv.reader(f, delimiter='\t')


def construire(ligne):
    if len(ligne) < 11:
        return None
    try:
        lat, lng = Decimal(ligne[9]), Decimal(ligne[10])
    except InvalidOperation:
        return None
    pays = ligne[0].upper()
    cp = normaliser_cp(ligne[1], pays)
    if not cp or not ligne[2]:
        return None
    return CodePostal(
        pays=pays, code_postal=cp, nom=ligne[2][:200], nom_normalise=normaliser_nom(ligne[2])[:200],
        region=ligne[3][:200], departement=ligne[5][:200], lat=lat, lng=lng)


class Command(BaseCommand):
    help = "Importe les codes postaux GeoNames (referentiel de geocodage local)."

    def add_arguments(self, parser):
        parser.add_argument('--pays', help='Codes ISO separes par des virgules (defaut : pays des equipes + FR)')
        parser.add_argument('--fichier', help='Fichier .zip ou .txt local (evite le telechargement)')

    def handle(self, *args, **options):
        if options['pays']:
            pays = [p.strip().upper() for p in options['pays'].split(',') if p.strip()]
        elif options['fichier']:
            pays = None
        else:
            pays = sorted(set(
                p.upper() for p in Equipe.objects.values_list('gerant_pays', flat=True).distinct() if p
            ) | {'FR'})
        if pays is not None:
            self.stdout.write('Pays : %s' % ', '.join(pays))

        par_pays = defaultdict(list)
        if options['fichier']:
            sources = [(options['fichier'], None)]
        else:
            sources = []
            for code in pays:
                f = tempfile.NamedTemporaryFile(suffix='.zip')
                self.stdout.write('Telechargement %s ...' % (URL % code))
                try:
                    with urllib.request.urlopen(URL % code, timeout=120) as r:
                        f.write(r.read())
                except Exception as e:
                    raise CommandError('Telechargement impossible (%s) : %s' % (code, e))
                f.flush()
                sources.append((f.name, f))
        for chemin, _ref in sources:
            for ligne in lire_lignes(chemin):
                if pays is not None and ligne and ligne[0].upper() not in pays:
                    continue
                obj = construire(ligne)
                if obj:
                    par_pays[obj.pays].append(obj)

        if not par_pays:
            raise CommandError('Aucune ligne importable.')
        with transaction.atomic():
            CodePostal.objects.filter(pays__in=list(par_pays)).delete()
            for code, objs in sorted(par_pays.items()):
                CodePostal.objects.bulk_create(objs, batch_size=BATCH)
                self.stdout.write('%s : %d codes postaux' % (code, len(objs)))
