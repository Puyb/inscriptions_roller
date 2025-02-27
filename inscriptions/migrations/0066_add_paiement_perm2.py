# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def add_perm(apps, schema_editor):
    User = apps.get_model('auth', 'user')
    Permission = apps.get_model('auth', 'permission')
    perms = Permission.objects.filter(codename__in=('add_paiement', 'change_paiement', 'delete_paiement',
                                                   'add_paiementrepartition', 'change_paiementrepartition', 'delete_paiementrepartition'))
    for perm in perms:
        for user in User.objects.exclude(user_permissions=perm):
            user.user_permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0065_add_paiement_perm'),
    ]

    operations = [
        migrations.RunPython(add_perm),
    ]
