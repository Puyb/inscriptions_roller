from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion
import django_resized.forms


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0097_course_to_edition'),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom')),
                ('uid', models.CharField(max_length=200, unique=True, validators=[RegexValidator(regex='^[a-z0-9]{3,}$', message='Ne doit contenir que des lettres ou des chiffres')], verbose_name='uid')),
                ('organisateur', models.CharField(max_length=200, verbose_name='Organisateur')),
                ('ville', models.CharField(max_length=200, verbose_name='Ville')),
                ('ville2', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='inscriptions.ville', verbose_name='Localisation', help_text="Origine du calcul des distances dans les statistiques. Renseignée automatiquement d'après la ville (France) ; à modifier pour une course à l'étranger.")),
                ('url', models.URLField(verbose_name='URL')),
                ('logo', django_resized.forms.ResizedImageField(blank=True, crop=None, force_format=None, keep_meta=False, null=True, quality=85, scale=None, size=[600, 600], upload_to='logo', verbose_name='Logo')),
                ('paypal', models.EmailField(blank=True, max_length=254, verbose_name='Adresse paypal')),
                ('frais_paypal_inclus', models.BooleanField(verbose_name='Frais paypal inclus')),
                ('stripe_secret', models.CharField(blank=True, max_length=200, null=True, verbose_name='Stripe Secret Key')),
                ('stripe_public', models.CharField(blank=True, max_length=200, null=True, verbose_name='Stripe Public Key')),
                ('stripe_endpoint_secret', models.CharField(blank=True, max_length=200, null=True, verbose_name='Stripe End Point Secret')),
                ('frais_stripe_inclus', models.BooleanField(verbose_name='Frais stripe inclus')),
                ('helloasso_organisation', models.CharField(blank=True, max_length=200, null=True, verbose_name='HelloAsso organization name')),
                ('helloasso_id', models.CharField(blank=True, max_length=200, null=True, verbose_name='HelloAsso clientId')),
                ('helloasso_secret', models.CharField(blank=True, max_length=200, null=True, verbose_name='HelloAsso clientSecret')),
                ('helloasso_sandbox', models.BooleanField(verbose_name='HelloAsso sandbox')),
                ('ordre', models.CharField(max_length=200, verbose_name='Ordre des chèques')),
                ('adresse', models.TextField(blank=True, verbose_name='Adresse')),
                ('active', models.BooleanField(default=False, verbose_name='Activée')),
            ],
        ),
        migrations.AddField(
            model_name='edition',
            name='course',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='editions', to='inscriptions.course'),
        ),
        migrations.AddField(
            model_name='edition',
            name='legacy_uid',
            field=models.CharField(blank=True, editable=False, max_length=200, null=True, unique=True, verbose_name='uid historique'),
        ),
    ]
