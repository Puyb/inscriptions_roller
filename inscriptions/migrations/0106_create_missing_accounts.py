from django.db import migrations


def create_missing_accounts(apps, schema_editor):
    """Cree l'Account (django-user-accounts) des utilisateurs qui n'en ont pas.

    Les anciennes versions de la lib toleraient son absence ; depuis la 3.3,
    `Account.for_request` (context processor) leve RelatedObjectDoesNotExist
    et le back-office devient inaccessible pour ces utilisateurs.
    """
    User = apps.get_model('auth', 'User')
    Account = apps.get_model('account', 'Account')
    for user in User.objects.filter(account__isnull=True):
        Account.objects.create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0105_course_description'),
        ('account', '0007_alter_emailconfirmation_sent'),
    ]

    operations = [
        migrations.RunPython(create_missing_accounts, migrations.RunPython.noop),
    ]
