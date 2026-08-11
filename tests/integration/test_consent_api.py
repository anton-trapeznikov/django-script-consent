import json

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from script_consent.cache import get_runtime_state
from script_consent.conf import app_settings
from script_consent.cookies import decode_consent_payload
from script_consent.models import (
    BannerConfig,
    ConsentRecord,
    ScriptCategory,
    ScriptSnippet,
)


class ConsentApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        ScriptSnippet.objects.all().delete()
        ConsentRecord.objects.all().delete()
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        BannerConfig.objects.create(
            title="Cookies", text="Text", version=1, is_active=True
        )
        ScriptSnippet.objects.create(
            name="Opt",
            category=self.analytics,
            placement="body_end",
            code="<!-- analytics -->",
        )

    def _csrf_headers(self):
        self.client.get("/")
        csrf = self.client.cookies.get("csrftoken")
        self.assertIsNotNone(csrf, "csrftoken cookie must be set")
        return {"HTTP_X_CSRFTOKEN": csrf.value}

    def test_accept_all(self):
        url = reverse("script_consent:accept")
        response = self.client.post(
            url,
            data=json.dumps({"action": "accept_all"}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("technical", data["categories"])
        self.assertIn("analytics", data["categories"])
        self.assertTrue(data["reload"])

        self.assertEqual(ConsentRecord.objects.count(), 1)
        rec = ConsentRecord.objects.get()
        self.assertEqual(rec.action, ConsentRecord.Action.ACCEPT_ALL)

        cookie_name = app_settings.CONSENT_COOKIE
        self.assertIn(cookie_name, response.cookies)
        payload = decode_consent_payload(response.cookies[cookie_name].value)
        self.assertEqual(payload["banner_version"], 1)
        self.assertEqual(payload["scripts_hash"], get_runtime_state()["scripts_hash"])

    def test_reject_optional(self):
        response = self.client.post(
            reverse("script_consent:accept"),
            data=json.dumps({"action": "reject_optional"}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["categories"], ["technical"])
        rec = ConsentRecord.objects.get()
        self.assertEqual(rec.action, ConsentRecord.Action.REJECT_OPTIONAL)

    def test_custom_forces_required(self):
        response = self.client.post(
            reverse("script_consent:accept"),
            data=json.dumps({"action": "custom", "categories": ["analytics"]}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        data = response.json()
        self.assertIn("technical", data["categories"])
        self.assertIn("analytics", data["categories"])

    def test_dismiss(self):
        response = self.client.post(
            reverse("script_consent:dismiss"),
            data="{}",
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(app_settings.DISMISS_COOKIE, response.cookies)
        self.assertEqual(ConsentRecord.objects.count(), 0)

    def test_withdraw_clears_cookies(self):
        self.client.post(
            reverse("script_consent:accept"),
            data=json.dumps({"action": "accept_all"}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.client.post(
            reverse("script_consent:dismiss"),
            data="{}",
            content_type="application/json",
            **self._csrf_headers(),
        )
        response = self.client.post(
            reverse("script_consent:withdraw"),
            data="{}",
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ConsentRecord.objects.filter(action=ConsentRecord.Action.WITHDRAW).count(),
            1,
        )
        consent_cookie = response.cookies.get(app_settings.CONSENT_COOKIE)
        self.assertIsNotNone(consent_cookie)
        self.assertIn(consent_cookie["max-age"], (0, "0"))
        dismiss = response.cookies.get(app_settings.DISMISS_COOKIE)
        self.assertIsNotNone(dismiss)
        self.assertIn(dismiss["max-age"], (0, "0"))

    def test_accept_without_active_banner(self):
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        cache.clear()
        response = self.client.post(
            reverse("script_consent:accept"),
            data=json.dumps({"action": "accept_all"}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "no_active_banner")
        self.assertEqual(ConsentRecord.objects.count(), 0)
