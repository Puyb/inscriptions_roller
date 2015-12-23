# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

def add_perms(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Permission = apps.get_model('auth', 'Permission')
    for user in User.objects.all():
        user.user_permissions.add(
            Permission.objects.get(codename='change_accreditation'),
            Permission.objects.get(codename='delete_accreditation'),
        )

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0011_auto_20151220_1824'),
    ]

    operations = [
            migrations.RunPython(add_perms),
    ]
