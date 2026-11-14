from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0099_regroupe_editions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='edition',
            name='course',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='editions', to='inscriptions.course'),
        ),
        migrations.RemoveField(model_name='edition', name='organisateur'),
        migrations.RemoveField(model_name='edition', name='ville'),
        migrations.RemoveField(model_name='edition', name='ville2'),
        migrations.RemoveField(model_name='edition', name='url'),
        migrations.RemoveField(model_name='edition', name='paypal'),
        migrations.RemoveField(model_name='edition', name='frais_paypal_inclus'),
        migrations.RemoveField(model_name='edition', name='stripe_secret'),
        migrations.RemoveField(model_name='edition', name='stripe_public'),
        migrations.RemoveField(model_name='edition', name='stripe_endpoint_secret'),
        migrations.RemoveField(model_name='edition', name='frais_stripe_inclus'),
        migrations.RemoveField(model_name='edition', name='helloasso_organisation'),
        migrations.RemoveField(model_name='edition', name='helloasso_id'),
        migrations.RemoveField(model_name='edition', name='helloasso_secret'),
        migrations.RemoveField(model_name='edition', name='helloasso_sandbox'),
        migrations.RemoveField(model_name='edition', name='ordre'),
        migrations.RemoveField(model_name='edition', name='adresse'),
    ]
