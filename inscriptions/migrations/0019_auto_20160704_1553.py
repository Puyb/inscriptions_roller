# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0018_auto_20160630_0110'),
    ]

    operations = [
        migrations.AddField(
            model_name='challenge',
            name='active',
            field=models.BooleanField(default=False, verbose_name='Activée'),
        ),
        migrations.AddField(
            model_name='challenge',
            name='logo',
            field=models.ImageField(upload_to='logo', blank=True, null=True, verbose_name='Logo'),
        ),
        migrations.AddField(
            model_name='challenge',
            name='uid',
            field=models.CharField(default='1467640408', unique=True, validators=[django.core.validators.RegexValidator(regex='^[a-z0-9]{3,}$', message='Ne doit contenir que des lettres ou des chiffres')], max_length=200, verbose_name='uid'),
            preserve_default=False,
        ),
    ]
