from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0085_categorie_couleur_dossard'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipe',
            name='penalite',
            field=models.IntegerField(default=0, verbose_name='Pénalité'),
        ),
        migrations.AddField(
            model_name='equipe',
            name='penalite_info',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Info pénalité'),
        ),
    ]
