# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0003_auto_20151129_2112'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='accreditation',
            name='course',
        ),
        migrations.AddField(
            model_name='accreditation',
            name='course',
            field=models.ForeignKey(default=None, related_name='accreditations', to='inscriptions.Course', on_delete=models.CASCADE),
            preserve_default=False,
        ),
    ]
