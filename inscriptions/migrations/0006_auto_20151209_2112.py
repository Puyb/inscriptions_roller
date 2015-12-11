# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0005_auto_20151206_1709'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='date_augmentation',
            field=models.DateField(null=True, blank=True, verbose_name="Date d'augmentation des tarifs"),
        ),
        migrations.AlterField(
            model_name='course',
            name='uid',
            field=models.CharField(validators=[django.core.validators.RegexValidator(regex='^[a-z0-9]{3,}$', message='Ne doit contenir que des lettres ou des chiffres')], unique=True, verbose_name='uid', max_length=200),
        ),
    ]
