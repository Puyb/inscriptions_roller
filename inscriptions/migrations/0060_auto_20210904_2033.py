# Generated by Django 2.0 on 2021-09-04 18:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0059_merge_20190815_1733'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='equipier',
            name='cerfa_valide',
        ),
        migrations.AlterField(
            model_name='equipe',
            name='verrou',
            field=models.BooleanField(default=False, verbose_name="Equipe verrouillée (modifiable uniquement par l'organisateur)"),
        ),
    ]
