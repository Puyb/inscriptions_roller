from django.db import migrations

from . import _course_mapping


def renomme(apps, schema_editor):
    """uid d'edition = celui du mapping (annee, suffixe si plusieurs epreuves) ;
    pour une edition hors mapping, l'annee, avec un suffixe en cas de doublon
    dans la meme course. L'ancien uid est conserve dans legacy_uid."""
    Edition = apps.get_model('inscriptions', 'Edition')
    pris = set()
    for edition in Edition.objects.order_by('course_id', 'date', 'id'):
        souhaite = _course_mapping.PAR_ANCIEN_UID.get(edition.legacy_uid, (None, None))[1]
        if not souhaite:
            souhaite = str(edition.date.year)
        uid, n = souhaite, 2
        while (edition.course_id, uid) in pris:
            uid = '%s-%d' % (souhaite, n)
            n += 1
        pris.add((edition.course_id, uid))
        edition.uid = uid
        edition.save(update_fields=['uid'])


def restaure(apps, schema_editor):
    Edition = apps.get_model('inscriptions', 'Edition')
    for edition in Edition.objects.exclude(legacy_uid=None):
        edition.uid = edition.legacy_uid
        edition.save(update_fields=['uid'])


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0102_edition_uid'),
    ]

    operations = [
        migrations.RunPython(renomme, restaure),
    ]
