from django.db import migrations


def renomme_permissions(apps, schema_editor, ancien='course', nouveau='edition'):
    Permission = apps.get_model('auth', 'Permission')
    for perm in Permission.objects.filter(content_type__app_label='inscriptions',
                                          content_type__model='edition'):
        for action in ('add', 'change', 'delete', 'view'):
            if perm.codename == '%s_%s' % (action, ancien):
                perm.codename = '%s_%s' % (action, nouveau)
                perm.name = perm.name.replace(ancien.capitalize(), nouveau.capitalize())
                perm.save()


def restaure_permissions(apps, schema_editor):
    renomme_permissions(apps, schema_editor, ancien='edition', nouveau='course')


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0096_course_ville2'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RenameModel('Course', 'Edition'),
        migrations.RunPython(renomme_permissions, restaure_permissions),
    ]
