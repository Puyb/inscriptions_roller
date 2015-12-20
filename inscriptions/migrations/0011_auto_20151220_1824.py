# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0010_activate_courses'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='organisateur',
            field=models.CharField(verbose_name='Organisateur', max_length=200, default='PUC Roller'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='accreditation',
            name='role',
            field=models.CharField(verbose_name='Role', max_length=20, default='', choices=[('', 'Accès interdit'), ('admin', 'Administrateur'), ('organisateur', 'Organisateur'), ('validateur', 'Validateur')], blank=True),
        ),
        migrations.AlterField(
            model_name='equipe',
            name='connu',
            field=models.CharField(verbose_name='Comment avez vous connu la course ?', max_length=200, choices=[('Site Roller en Ligne.com', 'Site Roller en Ligne.com'), ('Facebook', 'Facebook'), ('Presse', 'Presse'), ('Bouche à oreille', 'Bouche à oreille'), ('Flyer pendant une course', 'Flyer pendant une course'), ('Flyer pendant une randonnée', 'Flyer pendant une randonnée'), ('Affiche', 'Affiche'), ('Informations de la Mairie', 'Information de la Maire'), ('Par mon club', 'Par mon club'), ('Autre', 'Autre')]),
        ),
    ]
