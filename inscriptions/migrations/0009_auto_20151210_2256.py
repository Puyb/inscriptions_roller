# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0008_course_logo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='accreditation',
            name='active',
        ),
        migrations.AlterField(
            model_name='accreditation',
            name='role',
            field=models.CharField(choices=[('', 'Accès interdit'), ('admin', 'Administrateur'), ('organisateur', 'Organisateur'), ('validateur', 'Validateur')], verbose_name='Role', max_length=20, default=''),
        ),
    ]
