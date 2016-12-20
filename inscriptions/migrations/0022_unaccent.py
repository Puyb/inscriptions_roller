# -*- coding: utf-8 -*-
from django.db import migrations
from django.contrib.postgres.operations import UnaccentExtension


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0021_auto_20160728_1018'),
    ]

    operations = [
        UnaccentExtension(),
    ]
