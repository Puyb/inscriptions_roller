# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0026_add_mail_perm2'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveResult',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('position', models.IntegerField()),
                ('tours', models.IntegerField()),
                ('temps', models.DecimalField(max_digits=8, decimal_places=3)),
                ('meilleur_tour', models.DecimalField(max_digits=8, decimal_places=3)),
                ('penalité', models.IntegerField()),
                ('equipe', models.ForeignKey(to='inscriptions.Equipe', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='LiveSnapshot',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('date', models.DateTimeField()),
                ('received', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(to='inscriptions.Course', on_delete=models.CASCADE)),
            ],
        ),
        migrations.AddField(
            model_name='liveresult',
            name='snapshot',
            field=models.ForeignKey(to='inscriptions.LiveSnapshot', on_delete=models.CASCADE),
        ),
    ]
