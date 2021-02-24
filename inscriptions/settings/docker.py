from .default import *
import os

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS').split(',')
ADMINS = (
    (environ.get('EMAIL_ADMIN', ''), environ.EMAIL_ADMIN),
)

DEBUG = environ.get('DEBUG', '') == 'True'
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = environ.get('EMAIL_HOST', '')
EMAIL_PORT = environ.get('EMAIL_PORT', '')
EMAIL_HOST_USER = environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_MAIL = environ.get('DEFAULT_FROM_MAIL', '')

IMAP_HOST = environ.get('IMAP_HOST', '')
IMAP_PORT = environ.get('IMAP_PORT', '')
IMAP_USER = environ.get('IMAP_USER', '')
IMAP_PASSWORD = environ.get('IMAP_PASSWORD', '')

MAPQUEST_API_KEY = environ.get('MAPQUEST_API_KEY', '')

CONTACT_MAIL = environ.get('CONTACT_MAIL', '')

if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')
    INSTALLED_APPS.append('django_extensions')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ('127.0.0.1', )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": environ.get('DB_NAME', ''),
        "USER": environ.get('DB_USER', ''),
        "PASSWORD": environ.get('DB_PASSWORD', ''),
        "HOST": environ.get('DB_HOST', ''),
    }
}
