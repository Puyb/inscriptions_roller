from django.db import migrations


class Migration(migrations.Migration):
    """LiveSnapshot / LiveResult (suivi en direct) : fonctionnalite abandonnee, jamais utilisee."""

    dependencies = [
        ('inscriptions', '0087_templatemail_destinataire'),
    ]

    operations = [
        migrations.DeleteModel(name='LiveResult'),
        migrations.DeleteModel(name='LiveSnapshot'),
    ]
