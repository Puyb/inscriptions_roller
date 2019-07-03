from .default import *
try:
    from .local import *
except ImportError:
    pass
THEME_CONTACT_EMAIL = DEFAULT_FROM_EMAIL

CHANNEL_LAYERS["default"]["CONFIG"]["prefix"] = DATABASES["default"]["NAME"]
