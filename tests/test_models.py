from django.test import TestCase

from script_consent.models import (
    BannerConfig,
    ConsentRecord,
    ScriptCategory,
    ScriptSnippet,
)


class BannerConfigTests(TestCase):
    def setUp(self):
        BannerConfig.objects.all().delete()

    def test_version_bumps_on_title_or_text_change(self):
        banner = BannerConfig.objects.create(
            title="Title",
            text="Text",
            version=1,
            is_active=True,
        )
        self.assertEqual(banner.version, 1)

        banner.title = "New title"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 2)

        banner.text = "New text"
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 3)

    def test_version_does_not_bump_on_deactivate_only(self):
        banner = BannerConfig.objects.create(
            title="Title",
            text="Text",
            version=5,
            is_active=True,
        )
        banner.is_active = False
        banner.save()
        banner.refresh_from_db()
        self.assertEqual(banner.version, 5)

    def test_version_bumps_when_reactivated(self):
        banner = BannerConfig.objects.create(
            title="Title",
            text="Text",
            version=5,
            is_active=False,
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

    def test_get_solo_creates_default(self):
        BannerConfig.objects.all().delete()
        solo = BannerConfig.get_solo()
        self.assertTrue(solo.is_active)
        self.assertGreaterEqual(solo.version, 1)
        self.assertTrue(solo.title)


class ScriptSnippetTests(TestCase):
    def setUp(self):
        ScriptSnippet.objects.all().delete()
        self.required = ScriptCategory.objects.get(code="technical")
        self.optional = ScriptCategory.objects.get(code="analytics")

    def test_requires_consent_property(self):
        s1 = ScriptSnippet.objects.create(
            name="Session",
            category=self.required,
            code="<script></script>",
        )
        s2 = ScriptSnippet.objects.create(
            name="Metrika",
            category=self.optional,
            code="<script>/* m */</script>",
        )
        s3 = ScriptSnippet.objects.create(
            name="Always",
            category=self.optional,
            code="<script>/* always */</script>",
            always_load=True,
        )
        self.assertFalse(s1.requires_consent)
        self.assertTrue(s2.requires_consent)
        self.assertFalse(s3.requires_consent)

    def test_str_methods(self):
        category = ScriptCategory.objects.get(code="technical")
        script = ScriptSnippet.objects.create(
            name="X", category=category, code="<!-- x -->"
        )
        self.assertEqual(str(script), "X")
        self.assertEqual(str(category), category.title)

        record = ConsentRecord.objects.create(
            action=ConsentRecord.Action.ACCEPT_ALL,
            banner_version=1,
            scripts_hash="a" * 64,
        )
        self.assertIn(str(record.consent_id), str(record))
        self.assertIn("accept_all", str(record))

    def test_banner_config_str(self):
        banner = BannerConfig.objects.create(title="T", text="t", version=5)
        self.assertEqual(str(banner), "T (v5)")

    def test_get_solo_reactivates_inactive(self):
        BannerConfig.objects.all().delete()
        banner = BannerConfig.objects.create(
            title="Old", text="old", version=1, is_active=False
        )
        solo = BannerConfig.get_solo()
        self.assertEqual(solo.pk, banner.pk)
        solo.refresh_from_db()
        self.assertTrue(solo.is_active)

    def test_get_solo_creates_default_when_none(self):
        BannerConfig.objects.all().delete()
        solo = BannerConfig.get_solo()
        self.assertTrue(solo.is_active)
        self.assertTrue(solo.title)

    def test_save_version_bump_race_does_not_exist(self):
        banner = BannerConfig.objects.create(title="T", text="t", version=1)
        banner.title = "T2"
        # Simulate pk that no longer exists by deleting first
        BannerConfig.objects.filter(pk=banner.pk).delete()
        banner.save()
        # Should not raise; version stays as is
        self.assertEqual(banner.version, 1)
