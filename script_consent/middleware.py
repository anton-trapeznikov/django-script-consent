"""
Optional best-effort HTML injection for projects that cannot edit base templates.

Canonical integration remains template tags. This middleware injects scripts and
banner into text/html responses when markers are absent.

Ordering: place **after** ``GZipMiddleware`` in the MIDDLEWARE list (so this
middleware appears later in the list). ``process_response`` runs in reverse
order; ScriptConsent must rewrite uncompressed HTML, then GZip compresses.
"""

from __future__ import annotations

import re

from django.template.loader import render_to_string

from script_consent.utils import scripts_for_placement, should_show_banner


class ScriptConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        if getattr(response, "status_code", None) != 200:
            return response
        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response
        if getattr(response, "streaming", False):
            return response
        # Skip admin and likely API
        path = request.path or ""
        if path.startswith(("/admin/", "/script-consent/")):
            return response
        try:
            content = response.content.decode(response.charset or "utf-8")
        except (UnicodeDecodeError, AttributeError):
            return response

        # Avoid double-injection if template tags already used
        if (
            'id="script-consent-banner"' in content
            or "data-script-consent-root" in content
        ):
            return response

        from script_consent.conf import app_settings
        from script_consent.utils import (
            categories_for_banner,
            get_runtime_state,
            get_valid_consent,
            sanitize_privacy_policy_url,
        )

        consent = get_valid_consent(request)
        head = _join_codes(scripts_for_placement(request, "head", consent=consent))
        body_start = _join_codes(
            scripts_for_placement(request, "body_start", consent=consent)
        )
        body_end = _join_codes(
            scripts_for_placement(request, "body_end", consent=consent)
        )
        # Always inject banner shell + JS so withdraw/open work after consent
        runtime = get_runtime_state()
        banner_html = render_to_string(
            "script_consent/banner.html",
            {
                "show_consent_banner": should_show_banner(request, consent=consent),
                "show_settings_button": bool(app_settings.SHOW_SETTINGS_BUTTON),
                "script_consent_categories": categories_for_banner(),
                "script_consent_banner": runtime["banner"],
                "script_consent_privacy_url": sanitize_privacy_policy_url(
                    app_settings.PRIVACY_POLICY_URL
                ),
                "accepted_category_codes": list(consent.categories) if consent else [],
                "request": request,
            },
            request=request,
        )

        if head:
            content, n = re.subn(
                r"(?i)</head>",
                head + "\n</head>",
                content,
                count=1,
            )
            if n == 0:
                content = head + content

        if body_start:
            content, n = re.subn(
                r"(?i)<body([^>]*)>",
                lambda m: f"<body{m.group(1)}>\n{body_start}",
                content,
                count=1,
            )
            if n == 0:
                content = body_start + content

        tail = (banner_html or "") + (body_end or "")
        if tail:
            content, n = re.subn(
                r"(?i)</body>",
                tail + "\n</body>",
                content,
                count=1,
            )
            if n == 0:
                content = content + tail

        response.content = content.encode(response.charset or "utf-8")
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response


def _join_codes(scripts) -> str:
    if not scripts:
        return ""
    return "\n".join(s["code"] for s in scripts if s.get("code"))
