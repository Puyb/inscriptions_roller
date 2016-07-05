# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0019_auto_20160705_1108'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='distance',
            field=models.DecimalField(null=True, blank=True, max_digits=6, decimal_places=3, verbose_name="Distance d'un tour (en km)"),
        ),
        migrations.AddField(
            model_name='participationchallenge',
            name='position',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AlterUniqueTogether(
            name='equipechallenge',
            unique_together=set([('equipe', 'participation')]),
        ),
    ]
