from .default import *
try:
    from .local import *
except ImportError:
    pass
THEME_CONTACT_EMAIL = DEFAULT_FROM_EMAIL
