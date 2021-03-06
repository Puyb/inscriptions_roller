# Generated by Django 2.0 on 2019-07-03 21:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0054_auto_20190617_2326'),
    ]

    operations = [
        migrations.RenameField(
            model_name='mail',
            old_name='emeteur',
            new_name='emetteur',
        ),
        migrations.AlterField(
            model_name='mail',
            name='error',
            field=models.TextField(blank=True, max_length=200, null=True, verbose_name="Erreur d'envoi"),
        ),
        migrations.AlterField(
            model_name='mail',
            name='read',
            field=models.DateTimeField(default=None, null=True, verbose_name='Lu le'),
        ),
    ]
