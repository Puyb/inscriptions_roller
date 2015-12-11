# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0006_auto_20151209_2112'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='accreditation',
            unique_together=set([('user', 'course')]),
        ),
    ]
