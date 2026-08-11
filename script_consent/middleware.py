"""
Optional best-effort HTML injection for projects that cannot edit base templates.

Canonical integration remains template tags. This middleware injects scripts and
banner into text/html responses when markers are absent.

Ordering: place **after** ``GZipMiddleware`` in the MIDDLEWARE list (so this
middleware appears later in the list). ``process_response`` runs in reverse
order; ScriptConsent must rewrite uncompressed HTML, then GZip compresses.
"""

import re

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from script_consent import consent


class ScriptConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        if not _should_process(request, response):
            return response

        try:
            content = response.content.decode(response.charset or "utf-8")
        except (UnicodeDecodeError, AttributeError):
            return response

        if (
            'id="script-consent-banner"' in content
            or "data-script-consent-root" in content
        ):
            return response

        state = consent.get_valid_consent(request)
        head = _join_codes(
            consent.scripts_for_placement(request, "head", consent=state)
        )
        body_start = _join_codes(
            consent.scripts_for_placement(request, "body_start", consent=state)
        )
        body_end = _join_codes(
            consent.scripts_for_placement(request, "body_end", consent=state)
        )

        banner_html = render_to_string(
            "script_consent/banner.html",
            consent.banner_template_context(request, consent=state),
            request=request,
        )

        content = _inject_html(
            content,
            head=head,
            body_start=body_start,
            tail=(banner_html or "") + (body_end or ""),
        )
        response.content = content.encode(response.charset or "utf-8")
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))

        return response


def _should_process(request: HttpRequest, response: HttpResponse) -> bool:
    if getattr(response, "status_code", None) != 200:
        return False

    if "text/html" not in response.get("Content-Type", ""):
        return False

    if getattr(response, "streaming", False):
        return False

    path = request.path or ""
    return not path.startswith(("/admin/", "/script-consent/"))


def _inject_html(
    content: str,
    *,
    head: str,
    body_start: str,
    tail: str,
) -> str:
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

    if tail:
        content, n = re.subn(
            r"(?i)</body>",
            tail + "\n</body>",
            content,
            count=1,
        )
        if n == 0:
            content = content + tail

    return content


def _join_codes(scripts) -> str:
    if not scripts:
        return ""
    return "\n".join(s["code"] for s in scripts if s.get("code"))
