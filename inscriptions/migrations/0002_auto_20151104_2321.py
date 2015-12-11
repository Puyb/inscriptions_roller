# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='equipier',
            name='code_eoskates',
        ),
        migrations.RemoveField(
            model_name='equipier',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='equipier',
            name='piece_jointe2',
        ),
        migrations.RemoveField(
            model_name='equipier',
            name='piece_jointe2_valide',
        ),
    ]
