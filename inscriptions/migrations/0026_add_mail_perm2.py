# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def add_perm(apps, schema_editor):
    User = apps.get_model('auth', 'user')
    Permission = apps.get_model('auth', 'permission')
    perm = Permission.objects.get(codename='delete_mail')
    for user in User.objects.exclude(user_permissions=perm):
        user.user_permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0025_add_mail_perm'),
    ]

    operations = [
        migrations.RunPython(add_perm),
    ]