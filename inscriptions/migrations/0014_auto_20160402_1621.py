# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0013_mixte_libre'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='sexe',
            field=models.CharField(blank=True, choices=[('H', 'Homme'), ('F', 'Femme'), ('HX', 'Homme ou Mixte'), ('FX', 'Femme ou Mixte'), ('X', 'Mixte'), ('', 'Sans critères')], verbose_name='Sexe', max_length=2),
        ),
    ]
