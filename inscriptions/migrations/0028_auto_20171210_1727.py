# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0027_auto_20170401_1435'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='code',
            field=models.CharField(verbose_name='Code', max_length=200),
        ),
        migrations.AlterField(
            model_name='challengecategorie',
            name='code',
            field=models.CharField(verbose_name='Code', max_length=200),
        ),
    ]
