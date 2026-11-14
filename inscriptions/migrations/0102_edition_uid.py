from django.db import migrations, models
import inscriptions.models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0101_accreditation_course'),
    ]

    operations = [
        migrations.AlterField(
            model_name='edition',
            name='uid',
            field=models.CharField(help_text="Identifiant de l'édition dans l'adresse internet, par exemple l'année (2026). Unique pour une course.", max_length=200, validators=[inscriptions.models.EDITION_UID_VALIDATOR], verbose_name='uid'),
        ),
        migrations.AlterUniqueTogether(name='edition', unique_together={('course', 'uid')}),
        migrations.AlterField(
            model_name='course',
            name='uid',
            field=models.CharField(max_length=200, unique=True, validators=[inscriptions.models.COURSE_UID_VALIDATOR, inscriptions.models.valide_uid_course], verbose_name='uid'),
        ),
    ]
