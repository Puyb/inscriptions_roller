from datetime import datetime
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save

from django.contrib.auth.models import User, Permission
from .models import Paiement


@receiver(pre_save, sender=User)
def handle_user_presave(sender, instance, **kwargs):
    instance.is_staff = True

@receiver(post_save, sender=User)
def handle_user_postsave(sender, instance, **kwargs):
    instance.user_permissions.add(
        Permission.objects.get(codename='add_course'),
        Permission.objects.get(codename='change_course'),
        Permission.objects.get(codename='add_categorie'),
        Permission.objects.get(codename='change_categorie'),
        Permission.objects.get(codename='delete_categorie'),
        Permission.objects.get(codename='add_templatemail'),
        Permission.objects.get(codename='change_templatemail'),
        Permission.objects.get(codename='delete_templatemail'),
        Permission.objects.get(codename='add_equipe'),
        Permission.objects.get(codename='change_equipe'),
        Permission.objects.get(codename='delete_equipe'),
        Permission.objects.get(codename='change_equipier'),
        Permission.objects.get(codename='delete_equipier'),
        Permission.objects.get(codename='change_accreditation'),
        Permission.objects.get(codename='delete_accreditation'),
        Permission.objects.get(codename='change_mail'),
        Permission.objects.get(codename='delete_mail'),
        Permission.objects.get(codename='add_extraquestion'),
        Permission.objects.get(codename='change_extraquestion'),
        Permission.objects.get(codename='delete_extraquestion'),
        Permission.objects.get(codename='add_extraquestionchoice'),
        Permission.objects.get(codename='change_extraquestionchoice'),
        Permission.objects.get(codename='delete_extraquestionchoice'),
        Permission.objects.get(codename='add_paiement'),
        Permission.objects.get(codename='change_paiement'),
        Permission.objects.get(codename='delete_paiement'),
        Permission.objects.get(codename='add_paiementrepartition'),
        Permission.objects.get(codename='change_paiementrepartition'),
        Permission.objects.get(codename='delete_paiementrepartition'),
    )
