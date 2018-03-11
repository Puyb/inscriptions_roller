# Generated by Django 2.0 on 2018-01-09 13:33

from django.db import migrations

def add_perm(apps, schema_editor):
    User = apps.get_model('auth', 'user')
    Permission = apps.get_model('auth', 'permission')
    for perm in  Permission.objects.filter(codename__in=('add_extraquestionchoice', 'change_extraquestionchoice', 'delete_extraquestionchoice')):
        for user in User.objects.exclude(user_permissions=perm):
            user.user_permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0036_add_extra_perm'),
    ]

    operations = [
        migrations.RunPython(add_perm),
    ]