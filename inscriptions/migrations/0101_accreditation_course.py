from django.db import migrations, models
import django.db.models.deletion

PRIORITE = {'admin': 3, 'organisateur': 2, 'validateur': 1, '': 0}


def vers_course(apps, schema_editor):
    """Une accreditation par (utilisateur, course) : le role le plus eleve des
    accreditations de ses editions (admin > organisateur > validateur > en attente)."""
    Accreditation = apps.get_model('inscriptions', 'Accreditation')
    gardees = {}
    for acc in Accreditation.objects.select_related('course').order_by('id'):
        cle = (acc.user_id, acc.course.course_id)
        actuelle = gardees.get(cle)
        if actuelle is None:
            gardees[cle] = acc
        elif PRIORITE.get(acc.role, 0) > PRIORITE.get(actuelle.role, 0):
            actuelle.delete()
            gardees[cle] = acc
        else:
            acc.delete()
    for (_user, course_id), acc in gardees.items():
        acc.course_new_id = course_id
        acc.save(update_fields=['course_new'])


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0100_edition_sans_champs_course'),
    ]

    operations = [
        migrations.AlterUniqueTogether(name='accreditation', unique_together=set()),
        migrations.AddField(
            model_name='accreditation',
            name='course_new',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='inscriptions.course'),
        ),
        migrations.RunPython(vers_course, migrations.RunPython.noop),
        migrations.RemoveField(model_name='accreditation', name='course'),
        migrations.RenameField(model_name='accreditation', old_name='course_new', new_name='course'),
        migrations.AlterField(
            model_name='accreditation',
            name='course',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accreditations', to='inscriptions.course'),
        ),
        migrations.AlterUniqueTogether(name='accreditation', unique_together={('user', 'course')}),
    ]
