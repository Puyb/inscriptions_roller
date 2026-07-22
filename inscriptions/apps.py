from importlib import import_module

from django.apps import AppConfig as BaseAppConfig


class AppConfig(BaseAppConfig):

    name = "inscriptions"

    def ready(self):
        import_module("inscriptions.receivers")
        # Force pinax_theme_bootstrap's appconf (THEME_ADMIN_URL/THEME_CONTACT_EMAIL) to
        # configure itself onto django.conf.settings now, while it's still the real
        # settings object. If this import is instead first triggered later, lazily,
        # while some test's `override_settings(...)` is active (e.g. BaseTestCase's
        # MEDIA_ROOT override), appconf configures the *temporary* settings wrapper
        # instead, and the attributes are lost for good once that override is disabled.
        import_module("pinax_theme_bootstrap.conf")
