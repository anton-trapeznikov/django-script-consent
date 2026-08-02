from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from script_consent.admin import (
    BannerConfigAdmin,
    ConsentRecordAdmin,
    ScriptCategoryAdmin,
    ScriptSnippetAdmin,
)
from script_consent.models import (
    BannerConfig,
    ConsentRecord,
    ScriptCategory,
    ScriptSnippet,
)


class AdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

    def test_script_category_prepopulated_fields(self):
        admin = ScriptCategoryAdmin(ScriptCategory, self.site)
        self.assertIn("code", admin.prepopulated_fields)

    def test_script_snippet_code_preview_for_new_object(self):
        admin = ScriptSnippetAdmin(ScriptSnippet, self.site)
        self.assertEqual(admin.code_preview(None), "—")

    def test_script_snippet_code_preview_for_existing_object(self):
        category = ScriptCategory.objects.get(code="technical")
        script = ScriptSnippet.objects.create(
            name="S",
            category=category,
            code="<script>alert(1)</script>",
        )
        admin = ScriptSnippetAdmin(ScriptSnippet, self.site)
        preview = admin.code_preview(script)
        self.assertIn("alert(1)", preview)

    def test_banner_config_admin_readonly(self):
        admin = BannerConfigAdmin(BannerConfig, self.site)
        self.assertIn("version", admin.readonly_fields)

    def test_consent_record_permissions(self):
        request = self.factory.get("/")
        admin = ConsentRecordAdmin(ConsentRecord, self.site)
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

    def test_scripts_hash_short_long(self):
        record = ConsentRecord(scripts_hash="a" * 64)
        admin = ConsentRecordAdmin(ConsentRecord, self.site)
        self.assertEqual(admin.scripts_hash_short(record), "a" * 12 + "…")

    def test_scripts_hash_short_short(self):
        record = ConsentRecord(scripts_hash="abc")
        admin = ConsentRecordAdmin(ConsentRecord, self.site)
        self.assertEqual(admin.scripts_hash_short(record), "abc")
