# Generated by Django 2.0 on 2024-09-23 18:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0067_auto_20240923_1847'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='categorie',
            name='prix1',
        ),
        migrations.RemoveField(
            model_name='categorie',
            name='prix2',
        ),
        migrations.RemoveField(
            model_name='course',
            name='date_augmentation',
        ),
        migrations.RemoveField(
            model_name='extraquestion',
            name='price1',
        ),
        migrations.RemoveField(
            model_name='extraquestion',
            name='price2',
        ),
        migrations.RemoveField(
            model_name='extraquestionchoice',
            name='price1',
        ),
        migrations.RemoveField(
            model_name='extraquestionchoice',
            name='price2',
        ),
    ]
