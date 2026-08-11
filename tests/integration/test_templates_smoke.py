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
