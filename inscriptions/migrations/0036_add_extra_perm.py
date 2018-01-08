# Generated by Django 2.0 on 2018-01-08 12:39

from django.db import migrations

def add_perm(apps, schema_editor):
    User = apps.get_model('auth', 'user')
    Permission = apps.get_model('auth', 'permission')
    for perm in  Permission.objects.filter(codename__in=('add_extraquestion', 'change_extraquestion', 'delete_extraquestion')):
        for user in User.objects.exclude(user_permissions=perm):
            user.user_permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0035_templates'),
    ]

    operations = [
        migrations.RunPython(add_perm),
    ]
