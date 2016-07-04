# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0020_auto_20160704_2118'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challenge',
            name='courses',
            field=models.ManyToManyField(blank=True, to='inscriptions.Course', null=True),
        ),
    ]
