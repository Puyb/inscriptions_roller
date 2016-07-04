# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0019_challenge_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='challenge',
            name='active',
            field=models.BooleanField(verbose_name='Activée', default=False),
        ),
        migrations.AddField(
            model_name='challenge',
            name='uid',
            field=models.CharField(validators=[django.core.validators.RegexValidator(message='Ne doit contenir que des lettres ou des chiffres', regex='^[a-z0-9]{3,}$')], max_length=200, default='1467659892', verbose_name='uid', unique=True),
            preserve_default=False,
        ),
    ]
