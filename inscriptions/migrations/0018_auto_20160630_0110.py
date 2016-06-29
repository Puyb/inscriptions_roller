# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0017_auto_20160623_1445'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChallengeCategorie',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom')),
                ('code', models.CharField(max_length=10, verbose_name='Code')),
                ('min_equipiers', models.IntegerField(verbose_name="Nombre minimum d'équipiers")),
                ('max_equipiers', models.IntegerField(verbose_name="Nombre maximum d'équipiers")),
                ('min_age', models.IntegerField(verbose_name='Age minimum', default=12)),
                ('sexe', models.CharField(choices=[('H', 'Homme'), ('F', 'Femme'), ('HX', 'Homme ou Mixte'), ('FX', 'Femme ou Mixte'), ('X', 'Mixte'), ('', 'Sans critères')], max_length=2, verbose_name='Sexe', blank=True)),
                ('validation', models.TextField(verbose_name='Validation function (javascript)')),
                ('categories', models.ManyToManyField(related_name='_categories_+', to='inscriptions.Categorie')),
                ('challenge', models.ForeignKey(related_name='categories', to='inscriptions.Challenge')),
            ],
        ),
        migrations.AddField(
            model_name='participationchallenge',
            name='categorie',
            field=models.ForeignKey(related_name='participations', default=None, blank=True, to='inscriptions.ChallengeCategorie'),
        ),
    ]
