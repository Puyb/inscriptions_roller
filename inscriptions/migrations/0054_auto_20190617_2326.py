# Generated by Django 2.0 on 2019-06-17 21:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0053_auto_20190211_1342'),
    ]

    operations = [
        migrations.AddField(
            model_name='mail',
            name='error',
            field=models.TextField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='mail',
            name='read',
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='mail',
            name='uid',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
    ]
