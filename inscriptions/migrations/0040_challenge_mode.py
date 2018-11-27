# Generated by Django 2.0 on 2018-06-27 14:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0039_facture'),
    ]

    operations = [
        migrations.AddField(
            model_name='challenge',
            name='mode',
            field=models.CharField(choices=[('nord2017', 'Points / Participations (égalités possibles)'), ('nord2018', 'Points / Participations / Distance')], default='nord2017', max_length=20),
            preserve_default=False,
        ),
    ]