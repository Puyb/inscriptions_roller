# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def add_perm(apps, schema_editor):
    User = apps.get_model('auth', 'user')
    Permission = apps.get_model('auth', 'permission')
    perms = Permission.objects.filter(codename__in=('add_paiement', 'change_paiement', 'delete_paiement',
                                                   'add_paiement_repartition', 'change_paiement_repartition', 'delete_paiement_repartition'))
    for perm in perms:
        for user in User.objects.exclude(user_permissions=perm):
            user.user_permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0064_auto_20220404_1451'),
    ]

    operations = [
        migrations.RunPython(add_perm),
    ]
