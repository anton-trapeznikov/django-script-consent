import importlib

from django.apps import apps
from django.test import TestCase, override_settings

from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet

_fill_privacy = importlib.import_module(
    "script_consent.migrations.0005_fill_banner_privacy_url"
)


class SeedDataTests(TestCase):
    def test_default_categories_exist_after_migrate(self):
        codes = set(ScriptCategory.objects.values_list("code", flat=True))
        self.assertTrue({"technical", "analytics", "marketing"}.issubset(codes))
        tech = ScriptCategory.objects.get(code="technical")
        self.assertTrue(tech.is_required)
        self.assertTrue(BannerConfig.objects.filter(is_active=True).exists())
        banner = BannerConfig.objects.get(is_active=True)
        self.assertEqual(banner.privacy_url, "/privacy/")
        self.assertEqual(banner.version, 1)

    def test_demo_snippets_seeded_per_category(self):
        by_cat = {
            s.category.code: s
            for s in ScriptSnippet.objects.filter(
                name__startswith="Demo ·"
            ).select_related("category")
        }
        self.assertEqual(set(by_cat), {"technical", "analytics", "marketing"})
        self.assertIn("console.log", by_cat["technical"].code)


class FillPrivacyUrlMigrationTests(TestCase):
    def test_copies_custom_setting_without_bumping_version(self):
        BannerConfig.objects.all().update(privacy_url="", version=4)
        with override_settings(SCRIPT_CONSENT={"PRIVACY_POLICY_URL": "/legal/pdn/"}):
            _fill_privacy.fill_privacy_url(apps, None)
        banner = BannerConfig.objects.get(is_active=True)
        self.assertEqual(banner.privacy_url, "/legal/pdn/")
        self.assertEqual(banner.version, 4)

    def test_uses_default_when_setting_absent(self):
        BannerConfig.objects.all().update(privacy_url="")
        with override_settings(SCRIPT_CONSENT={"ANONYMIZE_IP": True}):
            _fill_privacy.fill_privacy_url(apps, None)
        banner = BannerConfig.objects.get(is_active=True)
        self.assertEqual(banner.privacy_url, "/privacy/")

    def test_uses_default_when_script_consent_missing(self):
        BannerConfig.objects.all().update(privacy_url="")
        with override_settings(SCRIPT_CONSENT=None):
            _fill_privacy.fill_privacy_url(apps, None)
        banner = BannerConfig.objects.get(is_active=True)
        self.assertEqual(banner.privacy_url, "/privacy/")

    def test_none_setting_leaves_empty(self):
        BannerConfig.objects.all().update(privacy_url="")
        with override_settings(SCRIPT_CONSENT={"PRIVACY_POLICY_URL": None}):
            _fill_privacy.fill_privacy_url(apps, None)
        self.assertEqual(BannerConfig.objects.get(is_active=True).privacy_url, "")
