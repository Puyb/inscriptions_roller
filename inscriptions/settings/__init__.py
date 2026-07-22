import os
import sys
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

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    # `manage.py test` never runs the "mail" channel consumer (see docstring in
    # inscriptions/consumers.py) so nothing ever drains it: with the real redis
    # backend, a large enough test run outgrows channels_redis' default 100-message
    # capacity and every subsequent send_mail() raises ChannelFull.
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer", "CONFIG": {"capacity": 10000}}}
else:
    CHANNEL_LAYERS["default"]["CONFIG"]["prefix"] = DATABASES["default"]["NAME"]
