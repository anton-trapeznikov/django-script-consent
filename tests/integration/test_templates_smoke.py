import uuid

from django.core.cache import cache
from django.template import RequestContext, Template
from django.test import RequestFactory, TestCase

from script_consent.consent import build_consent_state
from script_consent.cookies import encode_consent_payload
from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet


class TemplateTagsSmokeTests(TestCase):
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
            privacy_url="/privacy/",
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

    def test_scripts_respect_consent(self):
        request = self.factory.get("/")
        tpl = Template(
            "{% load script_consent %}"
            '{% consent_scripts "head" %}'
            '{% consent_scripts "body_end" %}'
        )
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("req-script", html)
        self.assertNotIn("opt-script", html)

        state = build_consent_state(uuid.uuid4(), [self.tech, self.analytics])
        request.COOKIES = {
            "script_consent": encode_consent_payload(state.to_dict()),
        }
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("opt-script", html)

    def test_banner_auto_open_without_consent(self):
        request = self.factory.get("/")
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="1"', html)
        self.assertIn("We use cookies", html)
        self.assertIn("script_consent/js/banner.js", html)

    def test_banner_shell_when_no_active_banner(self):
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        cache.clear()
        request = self.factory.get("/")
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        html = tpl.render(RequestContext(request, {}))
        self.assertIn("script-consent-banner", html)
        self.assertIn('data-auto-open="0"', html)

    def _render_banner(self):
        request = self.factory.get("/")
        tpl = Template("{% load script_consent %}{% consent_banner %}")
        return tpl.render(RequestContext(request, {}))

    def test_banner_default_has_close_hint_and_primary_on_selected(self):
        html = self._render_banner()
        self.assertIn("cc-banner__close-hint", html)
        self.assertIn("This is not consent to optional processing.", html)
        self.assertIn('data-cc-action="custom"', html)
        self.assertRegex(
            html,
            r'class="cc-btn cc-btn--primary" data-cc-action="custom"',
        )
        self.assertRegex(
            html,
            r'class="cc-btn cc-btn--secondary" data-cc-action="accept_all"',
        )
        self.assertNotIn("Recipients:", html)
        self.assertNotIn("cc-banner__operator", html)
        self.assertIn("Privacy policy", html)
        self.assertIn("data-impression-url=", html)

    def test_banner_shows_recipients_when_set(self):
        ScriptSnippet.objects.filter(category=self.analytics).update(
            recipient="Yandex Metrica"
        )
        cache.clear()
        html = self._render_banner()
        self.assertIn("Recipients: Yandex Metrica", html)

    def test_banner_uses_privacy_url_from_banner_config(self):
        BannerConfig.objects.filter(is_active=True).update(privacy_url="/legal/pdn/")
        cache.clear()
        html = self._render_banner()
        self.assertIn('href="/legal/pdn/"', html)
        self.assertNotIn('href="/privacy/"', html)

    def test_operator_footer_uses_banner_privacy_url(self):
        BannerConfig.objects.filter(is_active=True).update(
            operator="Acme LLC",
            privacy_url="/legal/pdn/",
        )
        cache.clear()
        html = self._render_banner()
        self.assertIn("cc-banner__operator", html)
        self.assertIn('href="/legal/pdn/"', html)
        self.assertNotIn("cc-banner__privacy", html)

    def test_banner_shows_operator_and_hides_top_privacy(self):
        BannerConfig.objects.filter(is_active=True).update(operator="Acme LLC, INN 123")
        cache.clear()
        html = self._render_banner()
        self.assertIn("cc-banner__operator", html)
        self.assertIn("Acme LLC, INN 123", html)
        self.assertIn("Personal data processing policy", html)
        self.assertNotIn("cc-banner__privacy", html)
