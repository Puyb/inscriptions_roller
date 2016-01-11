# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

def migrate_sexe(apps, schema_editor):
    Categorie = apps.get_model('inscriptions', 'Categorie')
    for cat in Categorie.objects.filter(sexe='X'):
        cat.sexe = ''
        cat.save()

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0012_auto_20160111_2113'),
    ]

    operations = [
        migrations.RunPython(migrate_sexe),
    ]
