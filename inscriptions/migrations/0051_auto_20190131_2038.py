# Generated by Django 2.0 on 2019-01-31 19:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0050_merge_20190131_0016'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equipier',
            name='cerfa_valide',
            field=models.BooleanField(verbose_name='Cerfa QS-SPORT'),
        ),
        migrations.AlterField(
            model_name='equipier',
            name='piece_jointe',
            field=models.FileField(blank=True, upload_to='certificats', verbose_name='Certificat ou licence'),
        ),
        migrations.AlterField(
            model_name='templatemail',
            name='destinataire',
            field=models.CharField(choices=[('Equipe', "Gerant d'équipe"), ('Equipier', 'Equipier'), ('Organisateur', 'Organisateur'), ('Paiement', 'Paiement'), ('Tous', 'Tous')], max_length=20, verbose_name='Destinataire'),
        ),
    ]