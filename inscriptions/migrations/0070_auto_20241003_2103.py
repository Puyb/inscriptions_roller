# Generated by Django 2.0 on 2024-10-03 19:03

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0069_merge_20241003_2044'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='prices',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=7), default=[], size=None, verbose_name='Prix'),
        ),
        migrations.AlterField(
            model_name='course',
            name='dates_augmentation',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DateField(), default=[], size=None, verbose_name="Date d'augmentation des tarifs"),
        ),
        migrations.AlterField(
            model_name='extraquestion',
            name='prices',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=7), default=[], size=None, verbose_name='Prix'),
        ),
        migrations.AlterField(
            model_name='extraquestionchoice',
            name='prices',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=7), default=[], size=None, verbose_name='Prix augmenté'),
        ),
    ]
