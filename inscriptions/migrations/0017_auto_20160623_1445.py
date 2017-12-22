# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0016_auto_20160623_1433'),
    ]

    operations = [
        migrations.RenameField(
            model_name='equipechallenge',
            old_name='particpation',
            new_name='participation',
        ),
        migrations.AlterField(
            model_name='participationchallenge',
            name='challenge',
            field=models.ForeignKey(to='inscriptions.Challenge', related_name='participations', on_delete=models.CASCADE),
        ),
    ]
