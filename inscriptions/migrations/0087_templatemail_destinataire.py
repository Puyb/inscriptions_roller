from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0086_equipe_penalite'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templatemail',
            name='destinataire',
            field=models.CharField(choices=[('Equipe', "Gerant d'équipe"), ('Organisateur', 'Organisateur')], default='Equipe', max_length=20, verbose_name='Destinataire'),
        ),
    ]
