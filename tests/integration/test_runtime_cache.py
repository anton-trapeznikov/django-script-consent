from django.core.cache import cache
from django.test import TestCase

from script_consent.cache import compute_scripts_hash, get_runtime_state
from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet


class RuntimeCacheIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        ScriptSnippet.objects.all().delete()
        self.cat = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        BannerConfig.objects.create(title="B", text="t", version=1, is_active=True)

    def test_hash_changes_when_script_code_saved(self):
        s = ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
        )
        h1 = compute_scripts_hash()
        s.code = "<script>2</script>"
        s.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)

    def test_banner_switch_invalidates_consent_binding(self):
        runtime = get_runtime_state()
        self.assertIsNotNone(runtime["banner"])
        first_id = runtime["banner"]["id"]
        BannerConfig.objects.create(
            title="Other", text="different", version=1, is_active=True
        )
        runtime2 = get_runtime_state()
        self.assertNotEqual(runtime2["banner"]["id"], first_id)

    def test_no_active_banner_runtime_shape(self):
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        cache.clear()
        runtime = get_runtime_state()
        self.assertIsNone(runtime["banner"])
        self.assertEqual(runtime["version"], 0)
        self.assertIn("scripts_hash", runtime)
