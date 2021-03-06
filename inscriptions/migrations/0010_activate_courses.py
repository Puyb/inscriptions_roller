# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.db import transaction

def activate_courses(apps, schema_editor):
    Course = apps.get_model('inscriptions', 'Course')
    User = apps.get_model('auth', 'User')
    with transaction.atomic():
        for course in Course.objects.all():
            if not course.accreditations.count():
                course.active = True
                course.save()
                for user in User.objects.all():
                    course.accreditations.create(user=user, role='admin')

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0009_auto_20151210_2256'),
    ]

    operations = [
        migrations.RunPython(activate_courses),
    ]
