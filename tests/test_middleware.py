from django.core.cache import cache
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, TestCase

from script_consent.middleware import ScriptConsentMiddleware
from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet


class ScriptConsentMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        ScriptSnippet.objects.all().delete()
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        BannerConfig.objects.create(title="B", text="t", version=1, is_active=True)
        ScriptSnippet.objects.create(
            name="Req",
            category=self.tech,
            placement="head",
            code='<script id="req-script">/*req*/</script>',
        )
        ScriptSnippet.objects.create(
            name="Opt",
            category=self.analytics,
            placement="body_end",
            code='<script id="opt-script">/*opt*/</script>',
        )

    def _middleware(self, response):
        def get_response(request):
            return response

        return ScriptConsentMiddleware(get_response)

    def test_skips_non_html_responses(self):
        request = RequestFactory().get("/")
        response = self._middleware(HttpResponse("plain", content_type="text/plain"))(
            request
        )
        self.assertEqual(response.content, b"plain")

    def test_skips_streaming_responses(self):
        request = RequestFactory().get("/")
        response = StreamingHttpResponse(["stream"])
        response["Content-Type"] = "text/html"
        processed = self._middleware(response)(request)
        self.assertIsInstance(processed, StreamingHttpResponse)

    def test_skips_admin_path(self):
        request = RequestFactory().get("/admin/")
        response = self._middleware(
            HttpResponse("<html></html>", content_type="text/html")
        )(request)
        self.assertEqual(response.content, b"<html></html>")

    def test_skips_script_consent_path(self):
        request = RequestFactory().get("/script-consent/accept/")
        response = self._middleware(
            HttpResponse("<html></html>", content_type="text/html")
        )(request)
        self.assertEqual(response.content, b"<html></html>")

    def test_skips_when_template_tag_present(self):
        request = RequestFactory().get("/")
        html = '<div id="script-consent-banner"></div>'
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        self.assertEqual(response.content.decode(), html)

    def test_injects_head_scripts(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("req-script", content)
        self.assertIn("</head>", content)

    def test_injects_body_start_scripts(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        ScriptSnippet.objects.create(
            name="BodyStart",
            category=self.tech,
            placement="body_start",
            code="<!-- body-start -->",
        )
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("body-start", content)

    def test_injects_banner_and_body_end(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("script-consent-banner", content)
        self.assertIn("banner.js", content)
        # Optional scripts must not appear without consent
        self.assertNotIn("opt-script", content)

    def test_skips_non_200_responses(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        response = HttpResponse(html, content_type="text/html", status=404)
        processed = self._middleware(response)(request)
        self.assertEqual(processed.content.decode(), html)
        self.assertNotIn("script-consent-banner", processed.content.decode())

    def test_injects_when_no_head_tag(self):
        request = RequestFactory().get("/")
        html = "<html><body></body></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("req-script", content)
        self.assertTrue(content.startswith("<script") or "<html>" in content)

    def test_injects_when_no_body_tag(self):
        request = RequestFactory().get("/")
        html = "<html><head></head></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("script-consent-banner", content)

    def test_content_length_updated(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        original = HttpResponse(html, content_type="text/html")
        original["Content-Length"] = str(len(html))
        response = self._middleware(original)(request)
        self.assertNotEqual(response["Content-Length"], str(len(html)))

    def test_handles_decode_error(self):
        request = RequestFactory().get("/")
        response = HttpResponse(b"\xff\xfe", content_type="text/html")
        response.charset = "utf-8"
        processed = self._middleware(response)(request)
        self.assertEqual(processed.content, b"\xff\xfe")

    def test_injects_body_start_when_no_body_tag(self):
        request = RequestFactory().get("/")
        ScriptSnippet.objects.create(
            name="BodyStart",
            category=self.tech,
            placement="body_start",
            code="<!-- body-start -->",
        )
        html = "<html><head></head></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("body-start", content)
