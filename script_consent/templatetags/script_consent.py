from django import template
from django.utils.safestring import mark_safe

from script_consent import consent

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

    scripts = consent.scripts_for_placement(request, placement)
    if not scripts:
        return ""

    parts = [s["code"] for s in scripts if s.get("code")]

    return mark_safe("\n".join(parts))


@register.inclusion_tag("script_consent/banner.html", takes_context=True)
def consent_banner(context):
    """Render banner shell, floating settings button, and JS (always)."""

    request = context.get("request")
    overrides: dict = {}

    if "script_consent_categories" in context:
        overrides["categories"] = context["script_consent_categories"]

    if "script_consent_banner" in context:
        overrides["banner"] = context["script_consent_banner"]

    if "script_consent_privacy_url" in context:
        overrides["privacy_url"] = context["script_consent_privacy_url"]

    if "current_consent" in context:
        overrides["consent"] = context["current_consent"]

    return consent.banner_template_context(request, **overrides)
