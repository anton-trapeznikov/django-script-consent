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

    def test_skips_non_html(self):
        request = RequestFactory().get("/")
        response = self._middleware(HttpResponse("plain", content_type="text/plain"))(
            request
        )
        self.assertEqual(response.content, b"plain")

    def test_skips_streaming(self):
        request = RequestFactory().get("/")
        response = StreamingHttpResponse(["stream"])
        response["Content-Type"] = "text/html"
        processed = self._middleware(response)(request)
        self.assertIsInstance(processed, StreamingHttpResponse)

    def test_skips_admin_path(self):
        request = RequestFactory().get("/admin/")
        html = b"<html></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        self.assertEqual(response.content, html)

    def test_skips_when_template_tag_present(self):
        request = RequestFactory().get("/")
        html = '<div id="script-consent-banner"></div>'
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        self.assertEqual(response.content.decode(), html)

    def test_injects_scripts_and_banner(self):
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("req-script", content)
        self.assertIn("script-consent-banner", content)
        self.assertIn('data-auto-open="1"', content)
        # optional without consent not injected
        self.assertNotIn("opt-script", content)

    def test_skips_non_200(self):
        request = RequestFactory().get("/")
        response = HttpResponse("<html></html>", content_type="text/html", status=404)
        processed = self._middleware(response)(request)
        self.assertEqual(processed.content, b"<html></html>")

    def test_no_active_banner_still_injects_required_scripts(self):
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        cache.clear()
        request = RequestFactory().get("/")
        html = "<html><head></head><body></body></html>"
        response = self._middleware(HttpResponse(html, content_type="text/html"))(
            request
        )
        content = response.content.decode()
        self.assertIn("req-script", content)
        self.assertIn('data-auto-open="0"', content)
