from .default import *
import os

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
ADMINS = (
    ('', mail) for mail in os.environ.get('EMAIL_ADMIN', '').split(',') if mail
)

DEBUG = os.environ.get('DEBUG', '') == 'True'
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', '')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', '')

MAPQUEST_API_KEY = os.environ.get('MAPQUEST_API_KEY', '')

CONTACT_MAIL = os.environ.get('CONTACT_MAIL', '')

if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')
    INSTALLED_APPS.append('django_extensions')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ('127.0.0.1', )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get('DB_NAME', ''),
        "USER": os.environ.get('DB_USER', ''),
        "PASSWORD": os.environ.get('DB_PASSWORD', ''),
        "HOST": os.environ.get('DB_HOST', ''),
    }
}
