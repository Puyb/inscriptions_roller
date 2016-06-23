# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0015_auto_20160605_1236'),
    ]

    operations = [
        migrations.CreateModel(
            name='Challenge',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('nom', models.CharField(max_length=200)),
                ('courses', models.ManyToManyField(to='inscriptions.Course')),
            ],
        ),
        migrations.CreateModel(
            name='EquipeChallenge',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('points', models.IntegerField()),
                ('equipe', models.ForeignKey(to='inscriptions.Equipe', related_name='challenge')),
            ],
        ),
        migrations.CreateModel(
            name='ParticipationChallenge',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('challenge', models.ForeignKey(to='inscriptions.Challenge', related_name='particpations')),
            ],
        ),
        migrations.AddField(
            model_name='equipechallenge',
            name='particpation',
            field=models.ForeignKey(to='inscriptions.ParticipationChallenge', related_name='equipes'),
        ),
    ]
