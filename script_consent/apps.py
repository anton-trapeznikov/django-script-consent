from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ScriptConsentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "script_consent"
    verbose_name = _("Script consent")

    def ready(self):
        from script_consent import signals  # noqa: F401
