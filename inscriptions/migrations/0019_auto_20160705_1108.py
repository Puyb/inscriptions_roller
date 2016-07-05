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
            field=models.BooleanField(verbose_name='Activée', default=False),
        ),
        migrations.AddField(
            model_name='challenge',
            name='logo',
            field=models.ImageField(upload_to='logo', verbose_name='Logo', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='challenge',
            name='uid',
            field=models.CharField(validators=[django.core.validators.RegexValidator(message='Ne doit contenir que des lettres ou des chiffres', regex='^[a-z0-9]{3,}$')], verbose_name='uid', max_length=200, unique=True, default='1467709701'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='challenge',
            name='courses',
            field=models.ManyToManyField(to='inscriptions.Course', null=True, blank=True),
        ),
    ]
