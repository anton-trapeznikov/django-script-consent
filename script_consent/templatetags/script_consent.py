from django import template
from django.utils.safestring import mark_safe

from script_consent.conf import app_settings
from script_consent.utils import (
    categories_for_banner,
    get_runtime_state,
    scripts_for_placement,
    should_show_banner,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def consent_scripts(context, placement: str):
    """
    Render active scripts for placement (head | body_start | body_end)
    allowed by current consent. Code is intentionally unescaped.
    """
    request = context.get("request")
    if request is None:
        return ""
    scripts = scripts_for_placement(request, placement)
    if not scripts:
        return ""
    parts = [s["code"] for s in scripts if s.get("code")]
    return mark_safe("\n".join(parts))


@register.inclusion_tag("script_consent/banner.html", takes_context=True)
def consent_banner(context):
    """Render banner shell, floating settings button, and JS (always)."""
    from script_consent.utils import get_valid_consent, sanitize_privacy_policy_url

    request = context.get("request")

    categories = context.get("script_consent_categories")
    banner = context.get("script_consent_banner")
    privacy_url = context.get("script_consent_privacy_url")

    if categories is None:
        categories = categories_for_banner()
    if banner is None:
        banner = get_runtime_state()["banner"]
    if privacy_url is None:
        privacy_url = sanitize_privacy_policy_url(app_settings.PRIVACY_POLICY_URL)
    else:
        privacy_url = sanitize_privacy_policy_url(privacy_url)

    consent = context.get("current_consent")
    # Distinguish missing key (re-fetch) from explicit None (no valid consent).
    if "current_consent" not in context and request is not None:
        consent = get_valid_consent(request)
    show = (
        should_show_banner(request, consent=consent) if request is not None else False
    )
    accepted = list(consent.categories) if consent else []

    return {
        "show_consent_banner": show,
        "show_settings_button": bool(app_settings.SHOW_SETTINGS_BUTTON),
        "script_consent_categories": categories,
        "script_consent_banner": banner,
        "script_consent_privacy_url": privacy_url,
        "accepted_category_codes": accepted,
        "request": request,
    }
