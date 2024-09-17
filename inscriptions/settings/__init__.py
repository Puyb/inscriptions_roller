import os
from .default import *
try:
    local_import_filename = os.environ.get('LOCAL_SETTINGS', '')
    if local_import_filename:
        from importlib import import_module
        module = import_module(local_import_filename, 'inscriptions.settings')
        for key in dir(module):
            globals()[key] = getattr(module, key)
    else:
        from .local import *
except ImportError:
    pass
THEME_CONTACT_EMAIL = DEFAULT_FROM_EMAIL

CHANNEL_LAYERS["default"]["CONFIG"]["prefix"] = DATABASES["default"]["NAME"]
