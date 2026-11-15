from datetime import date

from django.db import migrations, models
from django.db.models import Max


def archive_anciennes(apps, schema_editor):
    """Archive les courses dont la derniere edition date de plus de 2 ans."""
    Course = apps.get_model('inscriptions', 'Course')
    aujourdhui = date.today()
    limite = aujourdhui.replace(year=aujourdhui.year - 2, day=28) if (aujourdhui.month, aujourdhui.day) == (2, 29) \
        else aujourdhui.replace(year=aujourdhui.year - 2)
    Course.objects.annotate(derniere=Max('editions__date')).filter(derniere__lt=limite).update(archive=True)


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0103_edition_uid_par_course'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='archive',
            field=models.BooleanField(default=False, help_text="Course sans édition récente, listée dans « Anciennes courses ». Désactivé automatiquement à la création d'une nouvelle édition.", verbose_name='Archivée'),
        ),
        migrations.RunPython(archive_anciennes, migrations.RunPython.noop),
    ]
