from django.core.cache import cache
from django.template import Context, RequestContext, Template
from django.test import RequestFactory, TestCase

from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet
from script_consent.utils import (
    build_consent_state,
    encode_consent_payload,
    get_runtime_state,
)


class TemplateTagsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        ScriptSnippet.objects.all().delete()
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        BannerConfig.objects.create(
            title="We use cookies",
            text="Banner text",
            version=1,
            is_active=True,
        )
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

    def test_cookie_scripts_without_consent(self):
        request = self.factory.get("/")
        tpl = Template(
            "{% load script_consent %}"
            '{% consent_scripts "head" %}'
            '{% consent_scripts "body_end" %}'
        )
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("req-script", html)
        self.assertNotIn("opt-script", html)

    def test_cookie_scripts_with_consent(self):
        state = build_consent_state(
            __import__("uuid").uuid4(),
            [self.tech, self.analytics],
        )
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(state.to_dict()),
        }
        tpl = Template('{% load script_consent %}{% consent_scripts "body_end" %}')
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("opt-script", html)

    def test_banner_shown_without_consent(self):
        request = self.factory.get("/")
        runtime = get_runtime_state()
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(
            RequestContext(
                request,
                {
                    "script_consent_categories": runtime["categories"],
                    "script_consent_banner": runtime["banner"],
                    "script_consent_privacy_url": "/privacy/",
                },
            )
        )
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="1"', html)
        self.assertIn("We use cookies", html)
        self.assertIn("Necessary only", html)
        self.assertIn("Accept all", html)
        self.assertIn("banner.js", html)

    def test_banner_markup_always_present_when_dismissed(self):
        """JS API must load even when banner stays closed."""
        request = self.factory.get("/")
        request.COOKIES = {"script_banner_dismissed": "1"}
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="0"', html)
        self.assertIn("banner.js", html)

    def test_banner_api_present_with_valid_consent(self):
        state = build_consent_state(
            __import__("uuid").uuid4(),
            [self.tech, self.analytics],
        )
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(state.to_dict()),
        }
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="0"', html)
        self.assertIn("banner.js", html)
        self.assertIn("data-withdraw-url", html)
        self.assertIn("script-consent-launcher", html)
        self.assertIn("Consent settings", html)

    def test_launcher_hidden_attribute_when_auto_open(self):
        request = self.factory.get("/")
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-launcher", html)
        # When auto-open, launcher starts with hidden (JS also toggles)
        self.assertRegex(html, r'id="script-consent-launcher"[^>]*\bhidden\b')

    def test_cookie_scripts_without_request(self):
        tpl = Template('{% load script_consent %}{% consent_scripts "head" %}')
        html = tpl.render(Context({}))
        self.assertEqual(html, "")

    def test_cookie_banner_without_request(self):
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(Context({}))
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="0"', html)

    def test_cookie_banner_without_context_values(self):
        request = self.factory.get("/")
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-banner", html)
        self.assertIn("We use cookies", html)
