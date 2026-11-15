from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0104_course_archive'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='description',
            field=models.TextField(blank=True, help_text='Texte de présentation affiché sur la page de la course, à côté du logo, avant la liste des éditions.', verbose_name='Description'),
        ),
    ]
