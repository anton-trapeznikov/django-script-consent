from django.apps import AppConfig


class ExampleProjectConfig(AppConfig):
    """Demo project app: trim default admin to script_consent only."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "example_project"
    verbose_name = "Demo"

    def ready(self) -> None:
        from django.contrib import admin
        from django.contrib.auth.models import Group, User

        for model in (Group, User):
            if admin.site.is_registered(model):
                admin.site.unregister(model)

        admin.site.site_header = "django-script-consent demo"
        admin.site.site_title = "script-consent demo"
        admin.site.index_title = "Script consent"
