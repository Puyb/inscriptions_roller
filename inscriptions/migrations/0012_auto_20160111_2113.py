# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0011_auto_20151220_1824'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='sexe',
            field=models.CharField(choices=[('H', 'Homme'), ('F', 'Femme'), ('HX', 'Homme ou Mixte'), ('FX', 'Femme ou Mixte'), ('X', 'Mixte'), ('', 'Libre')], max_length=2, verbose_name='Sexe'),
        ),
        migrations.AlterField(
            model_name='equipe',
            name='connu',
            field=models.CharField(choices=[('Site Roller en Ligne.com', 'Site Roller en Ligne.com'), ('Facebook', 'Facebook'), ('Presse', 'Presse'), ('Bouche à oreille', 'Bouche à oreille'), ('Flyer pendant une course', 'Flyer pendant une course'), ('Flyer pendant une randonnée', 'Flyer pendant une randonnée'), ('Affiche', 'Affiche'), ('Informations de la Mairie', 'Information de la Mairie'), ('Par mon club', 'Par mon club'), ('Autre', 'Autre')], max_length=200, verbose_name='Comment avez vous connu la course ?'),
        ),
    ]
