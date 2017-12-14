# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0020_auto_20160705_1733'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challenge',
            name='courses',
            field=models.ManyToManyField(null=True, related_name='challenges', blank=True, to='inscriptions.Course'),
        ),
        migrations.AlterField(
            model_name='equipechallenge',
            name='equipe',
            field=models.ForeignKey(related_name='challenges', to='inscriptions.Equipe', on_delete=models.CASCADE),
        ),
    ]
