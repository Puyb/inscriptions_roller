# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inscriptions', '0002_auto_20151104_2321'),
    ]

    operations = [
        migrations.CreateModel(
            name='Accreditation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('role', models.CharField(verbose_name='Role', choices=[('admin', 'Administrateur'), ('organisateur', 'Organisateur'), ('validateur', 'Validateur')], max_length=20)),
                ('course', models.ManyToManyField(related_name='accreditations', to='inscriptions.Course')),
                ('user', models.ForeignKey(related_name='accredidations', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='course',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='user',
        ),
        migrations.DeleteModel(
            name='UserProfile',
        ),
    ]
