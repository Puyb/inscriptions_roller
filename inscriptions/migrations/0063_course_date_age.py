# Generated by Django 2.0 on 2022-02-10 21:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0062_auto_20220204_2223'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='date_age',
            field=models.DateField(blank=True, default=None, help_text='Date à utiliser pour le calcul des sage. Laisser vide pour utiliser la date de la course', null=True, verbose_name='Date calcul ages'),
        ),
    ]