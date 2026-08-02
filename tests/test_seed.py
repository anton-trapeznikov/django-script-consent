from django.test import TestCase

from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet


class SeedDataTests(TestCase):
    def test_default_categories_exist_after_migrate(self):
        # migrations already applied by TestCase
        codes = set(ScriptCategory.objects.values_list("code", flat=True))
        self.assertTrue({"technical", "analytics", "marketing"}.issubset(codes))
        tech = ScriptCategory.objects.get(code="technical")
        self.assertTrue(tech.is_required)
        self.assertTrue(BannerConfig.objects.filter(is_active=True).exists())

    def test_demo_snippets_seeded_per_category(self):
        by_cat = {
            s.category.code: s
            for s in ScriptSnippet.objects.filter(
                name__startswith="Demo ·"
            ).select_related("category")
        }
        self.assertEqual(set(by_cat), {"technical", "analytics", "marketing"})
        self.assertIn("console.log", by_cat["technical"].code)
        self.assertIn("console.log", by_cat["analytics"].code)
        self.assertIn("console.log", by_cat["marketing"].code)
        self.assertEqual(by_cat["technical"].placement, "head")
        self.assertEqual(by_cat["analytics"].placement, "body_end")
