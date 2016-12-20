# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib.postgres.operations import CreateExtension

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0022_unaccent'),
    ]

    operations = [
        CreateExtension('fuzzystrmatch'),
    ]
