# Generated by Django 2.0 on 2019-07-09 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0057_remove_paiement_stripe_charge'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='stripe_endpoint_secret',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Stripe End Point Secret'),
        ),
    ]
