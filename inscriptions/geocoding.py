"""Geocodage local des communes a partir du referentiel `CodePostal` (GeoNames).

Aucun appel reseau : voir `docs/stats-repair-plan.md`.
"""
import re
import unicodedata

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
