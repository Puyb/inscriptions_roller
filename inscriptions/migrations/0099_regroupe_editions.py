import logging
import re

from django.db import migrations

from . import _course_mapping

logger = logging.getLogger(__name__)

CHAMPS_COURSE = (
    'organisateur', 'ville', 'ville2_id', 'url',
    'paypal', 'frais_paypal_inclus',
    'stripe_secret', 'stripe_public', 'stripe_endpoint_secret', 'frais_stripe_inclus',
    'helloasso_organisation', 'helloasso_id', 'helloasso_secret', 'helloasso_sandbox',
    'ordre', 'adresse', 'logo', 'active',
)


def uid_course_libre(uid, pris):
    """Uid de course pour une edition absente du mapping : jamais egal a un
    legacy_uid (sinon /<uid>/ serait ambigu), conforme a ^[a-z0-9]{3,}$."""
    base = re.sub('[^a-z0-9]', '', uid.lower()) or 'course'
    candidat = base + 'c'
    while len(candidat) < 3 or candidat in pris:
        candidat += 'c'
    return candidat


def regroupe(apps, schema_editor):
    Course = apps.get_model('inscriptions', 'Course')
    Edition = apps.get_model('inscriptions', 'Edition')

    def principale(edition):
        # a date egale (3h et 6h le meme jour), l'edition « principale » (uid
        # d'edition = l'annee seule) passe avant les variantes (« 2023-6h »)
        uid = _course_mapping.PAR_ANCIEN_UID.get(edition.uid, ('', ''))[1]
        return 0 if uid.isdigit() or not uid else 1

    editions = sorted(Edition.objects.all(), key=lambda e: (-e.date.toordinal(), principale(e), -e.id))
    legacy = {e.uid for e in editions}
    collisions = legacy & set(_course_mapping.COURSES)
    if collisions:
        raise RuntimeError("uid de course en collision avec un uid d'edition existant : %s" % sorted(collisions))

    groupes = {}  # uid de course -> [editions, la plus recente d'abord]
    noms = {}
    pris = set(_course_mapping.COURSES) | legacy
    for edition in editions:
        if edition.uid in _course_mapping.PAR_ANCIEN_UID:
            uid_course = _course_mapping.PAR_ANCIEN_UID[edition.uid][0]
            noms[uid_course] = _course_mapping.COURSES[uid_course]['nom']
        else:
            uid_course = uid_course_libre(edition.uid, pris)
            pris.add(uid_course)
            noms[uid_course] = edition.nom
            logger.warning("Edition %s absente du mapping : course %s creee", edition.uid, uid_course)
        groupes.setdefault(uid_course, []).append(edition)

    for uid_course, membres in groupes.items():
        derniere = membres[0]
        valeurs = {champ: getattr(derniere, champ) for champ in CHAMPS_COURSE}
        # le logo de la course vient de la derniere edition qui en a un
        valeurs['logo'] = next((e.logo for e in membres if e.logo), '')
        course = Course.objects.create(uid=uid_course, nom=noms[uid_course], **valeurs)
        for edition in membres:
            edition.course = course
            edition.legacy_uid = edition.uid
            edition.save(update_fields=['course', 'legacy_uid'])


def defait(apps, schema_editor):
    apps.get_model('inscriptions', 'Edition').objects.update(course=None, legacy_uid=None)
    apps.get_model('inscriptions', 'Course').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0098_course_model'),
    ]

    operations = [
        migrations.RunPython(regroupe, defait),
    ]
