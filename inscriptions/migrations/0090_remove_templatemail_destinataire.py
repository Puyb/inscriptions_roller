from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0089_templatemail_equipe_uniquement'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='templatemail',
            name='destinataire',
        ),
    ]
