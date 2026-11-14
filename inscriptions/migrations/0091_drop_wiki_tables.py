from django.db import migrations

# Le wiki django-wiki a ete remplace par une documentation statique (mkdocs, dossier docs/wiki).
# On supprime les tables laissees par les applications wiki et sorl.thumbnail.
TABLES = [
    'wiki_attachments_attachmentrevision', 'wiki_attachments_attachment',
    'wiki_images_imagerevision', 'wiki_images_image',
    'wiki_notifications_articlesubscription',
    'wiki_reusableplugin_articles', 'wiki_reusableplugin',
    'wiki_revisionpluginrevision', 'wiki_revisionplugin',
    'wiki_simpleplugin', 'wiki_articleplugin',
    'wiki_articleforobject', 'wiki_urlpath',
    'wiki_articlerevision', 'wiki_article',
    'thumbnail_kvstore',
]


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0090_remove_templatemail_destinataire'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS {t} CASCADE;' for t in TABLES],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
