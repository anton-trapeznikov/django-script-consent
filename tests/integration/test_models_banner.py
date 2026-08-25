from django.test import TestCase

from script_consent.models import (
    BannerConfig,
    RuntimeCacheStamp,
    ScriptCategory,
    ScriptSnippet,
)
from script_consent.repositories import increment_banner_counter


class BannerConfigTests(TestCase):
    def setUp(self):
        BannerConfig.objects.all().delete()

    def test_version_bumps_on_title_change(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=1, is_active=True
        )
        banner.title = "New title"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 2)

    def test_version_bumps_on_text_change(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=1, is_active=True
        )
        banner.text = "New text"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 2)

    def test_version_does_not_bump_on_deactivate_only(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=5, is_active=True
        )
        banner.is_active = False
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 5)

    def test_version_bumps_when_reactivated(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=5, is_active=False
        )
        banner.is_active = True
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 6)

    def test_only_one_active_banner(self):
        a = BannerConfig.objects.create(title="A", text="a", is_active=True)
        b = BannerConfig.objects.create(title="B", text="b", is_active=True)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)

    def test_get_solo_returns_none_when_empty(self):
        self.assertIsNone(BannerConfig.get_solo())
        self.assertEqual(BannerConfig.objects.count(), 0)

    def test_get_solo_returns_none_when_only_inactive(self):
        BannerConfig.objects.create(title="Old", text="old", version=1, is_active=False)
        self.assertIsNone(BannerConfig.get_solo())
        self.assertFalse(BannerConfig.objects.filter(is_active=True).exists())

    def test_get_solo_returns_existing_active(self):
        active = BannerConfig.objects.create(
            title="Active", text="a", version=3, is_active=True
        )
        BannerConfig.objects.create(
            title="Inactive", text="i", version=1, is_active=False
        )
        solo = BannerConfig.get_solo()
        self.assertEqual(solo.pk, active.pk)
        self.assertEqual(solo.version, 3)

    def test_save_does_not_bump_version_when_row_missing(self):
        banner = BannerConfig.objects.create(title="T", text="t", version=1)
        banner.title = "T2"
        BannerConfig.objects.filter(pk=banner.pk).delete()
        banner.save()
        self.assertEqual(banner.version, 1)

    def test_version_bumps_on_privacy_url_change(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=1, is_active=True
        )
        banner.privacy_url = "/legal/privacy/"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 2)

    def test_version_bumps_on_operator_change(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=1, is_active=True
        )
        banner.operator = "Acme LLC"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 2)

    def test_version_does_not_bump_on_counter_update(self):
        banner = BannerConfig.objects.create(
            title="Title", text="Text", version=4, is_active=True
        )
        generation = RuntimeCacheStamp.current()
        updated = increment_banner_counter(banner.pk, "impressions")
        banner.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertEqual(banner.impressions, 1)
        self.assertEqual(banner.version, 4)
        self.assertEqual(RuntimeCacheStamp.current(), generation)

    def test_stats_default_to_zero_and_operator_empty(self):
        banner = BannerConfig.objects.create(title="Title", text="Text")
        self.assertEqual(banner.operator, "")
        self.assertEqual(banner.impressions, 0)
        self.assertEqual(banner.dismissals, 0)
        self.assertEqual(banner.necessary_only, 0)
        self.assertEqual(banner.custom_saves, 0)
        self.assertEqual(banner.accept_all, 0)

    def test_increment_unknown_field_raises(self):
        banner = BannerConfig.objects.create(title="Title", text="Text")
        with self.assertRaises(ValueError):
            increment_banner_counter(banner.pk, "version")


class ScriptSnippetRequiresConsentTests(TestCase):
    def setUp(self):
        ScriptSnippet.objects.all().delete()
        self.required, _ = ScriptCategory.objects.get_or_create(
            code="technical",
            defaults={
                "title": "Essential",
                "is_required": True,
                "order": 0,
                "is_active": True,
            },
        )
        self.optional, _ = ScriptCategory.objects.get_or_create(
            code="analytics",
            defaults={
                "title": "Analytics",
                "is_required": False,
                "order": 10,
                "is_active": True,
            },
        )

    def test_requires_consent_false_for_required_category(self):
        snippet = ScriptSnippet.objects.create(
            name="Session",
            category=self.required,
            code="<script></script>",
        )
        self.assertFalse(snippet.requires_consent)

    def test_requires_consent_true_for_optional_category(self):
        snippet = ScriptSnippet.objects.create(
            name="Metrika",
            category=self.optional,
            code="<script>/* m */</script>",
        )
        self.assertTrue(snippet.requires_consent)

    def test_requires_consent_false_when_always_load(self):
        snippet = ScriptSnippet.objects.create(
            name="Always",
            category=self.optional,
            code="<script>/* always */</script>",
            always_load=True,
        )
        self.assertFalse(snippet.requires_consent)

    def test_recipient_defaults_empty(self):
        snippet = ScriptSnippet.objects.create(
            name="Metrika",
            category=self.optional,
            code="<script>/* m */</script>",
        )
        self.assertEqual(snippet.recipient, "")
