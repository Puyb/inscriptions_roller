# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0004_auto_20151129_2236'),
    ]

    operations = [
        migrations.AddField(
            model_name='accreditation',
            name='active',
            field=models.BooleanField(verbose_name='Activée', default=False),
        ),
        migrations.AddField(
            model_name='course',
            name='active',
            field=models.BooleanField(verbose_name='Activée', default=False),
        ),
        migrations.AlterField(
            model_name='accreditation',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='accreditations'),
        ),
    ]
