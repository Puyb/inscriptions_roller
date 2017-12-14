# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0023_fuzzystrmatch'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mail',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('emeteur', models.EmailField(max_length=254)),
                ('destinataires', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254), size=None)),
                ('bcc', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254), blank=True, size=None)),
                ('sujet', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('date', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(to='inscriptions.Course', on_delete=models.CASCADE)),
                ('equipe', models.ForeignKey(to='inscriptions.Equipe', null=True, on_delete=models.SET_NULL)),
                ('template', models.ForeignKey(to='inscriptions.TemplateMail', null=True, on_delete=models.SET_NULL)),
            ],
        ),
        migrations.AlterField(
            model_name='challengecategorie',
            name='categories',
            field=models.ManyToManyField(related_name='challenge_categories', to='inscriptions.Categorie'),
        ),
        migrations.AlterField(
            model_name='equipier',
            name='autorisation',
            field=models.FileField(help_text="Si vous le pouvez, scannez l'autorisation et ajoutez la en pièce jointe (formats PDF ou JPEG).\nVous pourrez aussi la télécharger plus tard, ou l'envoyer par courrier (%(link)s)", upload_to='certificats', blank=True, verbose_name='Autorisation parentale'),
        ),
        migrations.AlterField(
            model_name='equipier',
            name='date_de_naissance',
            field=models.DateField(help_text='Chaque équipier doit avoir plus de %(min_age)s ans au %(date)s.', verbose_name='Date de naissance'),
        ),
        migrations.AlterField(
            model_name='equipier',
            name='justificatif',
            field=models.CharField(help_text="Chaque équipier doit avoir un certificat médical de moins d'un an ou une licence FFRS en cours de validité pour participer.", choices=[('licence', 'Licence FFRS'), ('certificat', 'Certificat médical')], verbose_name='Justificatif', max_length=15),
        ),
        migrations.AlterField(
            model_name='equipier',
            name='piece_jointe',
            field=models.FileField(help_text="Si vous le pouvez, scannez le certificat ou la licence et ajoutez le en pièce jointe (formats PDF ou JPEG).\nVous pourrez aussi le télécharger plus tard, ou l'envoyer par courrier (%(link)s).", upload_to='certificats', blank=True, verbose_name='Certificat ou licence'),
        ),
    ]
