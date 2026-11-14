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


def sql_renomme_objets(table, ancien, nouveau):
    """RenameModel ne renomme pas les index, contraintes et sequences : ils
    garderaient le prefixe de l'ancienne table et entreraient en collision avec
    ceux de la future table inscriptions_course."""
    return """
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT indexname FROM pg_indexes
             WHERE schemaname = current_schema() AND tablename = '%(t)s'
               AND indexname LIKE 'inscriptions_%(a)s%%' LOOP
        EXECUTE format('ALTER INDEX %%I RENAME TO %%I', r.indexname,
                       regexp_replace(r.indexname, '^inscriptions_%(a)s', 'inscriptions_%(n)s'));
    END LOOP;
    FOR r IN SELECT conname FROM pg_constraint
             WHERE conrelid = '%(t)s'::regclass
               AND conname LIKE 'inscriptions_%(a)s%%' AND contype <> 'p' LOOP
        EXECUTE format('ALTER TABLE %(t)s RENAME CONSTRAINT %%I TO %%I', r.conname,
                       regexp_replace(r.conname, '^inscriptions_%(a)s', 'inscriptions_%(n)s'));
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'inscriptions_%(a)s_id_seq') THEN
        ALTER SEQUENCE inscriptions_%(a)s_id_seq RENAME TO inscriptions_%(n)s_id_seq;
    END IF;
END $$;
""" % {'t': table, 'a': ancien, 'n': nouveau}


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0096_course_ville2'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RenameModel('Course', 'Edition'),
        migrations.RunSQL(sql_renomme_objets('inscriptions_edition', 'course', 'edition'),
                      sql_renomme_objets('inscriptions_edition', 'edition', 'course')),
        migrations.RunPython(renomme_permissions, restaure_permissions),
    ]
