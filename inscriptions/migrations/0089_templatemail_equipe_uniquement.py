from django.db import migrations
from django.db.models import Q

ADMIN_TEMPLATES = ('inscription_admin', 'changement_numero_admin', 'paiement_admin')


def forwards(apps, schema_editor):
    TemplateMail = apps.get_model('inscriptions', 'TemplateMail')
    # Les notifications organisateur (inscription_admin, changement_numero_admin,
    # paiement_admin) ne passent plus par TemplateMail : le code rend directement
    # mails/<nom>.html. Leurs modeles (un simple {% include %}) n'ont plus d'utilite,
    # y compris les rares copies mal configurees avec un autre destinataire.
    TemplateMail.objects.filter(
        Q(destinataire='Organisateur') | Q(nom__in=ADMIN_TEMPLATES)
    ).delete()
    # Les equipiers n'ont pas d'adresse e-mail : les modeles 'Equipier' et 'Tous'
    # deviennent des modeles pour les equipes (envoi au gerant).
    TemplateMail.objects.exclude(destinataire='Equipe').update(destinataire='Equipe')


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0088_delete_live_models'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
