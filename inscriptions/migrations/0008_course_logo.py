# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0007_auto_20151209_2344'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='logo',
            field=models.ImageField(verbose_name='Logo', upload_to='logo', blank=True, null=True),
        ),
    ]
