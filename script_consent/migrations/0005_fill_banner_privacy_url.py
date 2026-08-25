from django.conf import settings
from django.db import migrations


_DEFAULT_PRIVACY_URL = "/privacy/"


def _privacy_url_from_settings() -> str:
    user_settings = getattr(settings, "SCRIPT_CONSENT", None) or {}
    if isinstance(user_settings, dict) and "PRIVACY_POLICY_URL" in user_settings:
        raw = user_settings["PRIVACY_POLICY_URL"]
    else:
        raw = _DEFAULT_PRIVACY_URL
    if not raw:
        return ""
    return str(raw).strip()


def fill_privacy_url(apps, schema_editor):
    BannerConfig = apps.get_model("script_consent", "BannerConfig")
    BannerConfig.objects.filter(privacy_url="").update(privacy_url=_privacy_url_from_settings())


class Migration(migrations.Migration):

    dependencies = [
        ("script_consent", "0004_banner_privacy_url"),
    ]

    operations = [
        migrations.RunPython(fill_privacy_url, migrations.RunPython.noop),
    ]
