# Generated by Django 2.0 on 2019-01-29 21:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0042_auto_20180709_2319'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipier',
            name='cerfa_valide',
            field=models.BooleanField(default=False, verbose_name='Je certifie que cette personne a renseigné le questionnaire de santé QS-SPORT Cerfa N°15699*01 et a répondu par la négative à l’ensemble des questions'),
            preserve_default=False,
        ),
    ]
