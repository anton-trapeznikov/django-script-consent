from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from script_consent import admin as sc_admin
from script_consent import models as sc_models


class ScriptSnippetAdminDisplayTests(SimpleTestCase):
    def setUp(self):
        self.admin = sc_admin.ScriptSnippetAdmin(sc_models.ScriptSnippet, AdminSite())

    def test_code_preview_new_object(self):
        self.assertEqual(self.admin.code_preview(None), "—")

    def test_code_preview_existing(self):
        obj = sc_models.ScriptSnippet(pk=1, code="<script>alert(1)</script>")
        preview = self.admin.code_preview(obj)
        self.assertIn("alert(1)", preview)
        self.assertIn("<pre", preview)

    def test_code_preview_truncates(self):
        obj = sc_models.ScriptSnippet(pk=1, code="x" * 600)
        preview = self.admin.code_preview(obj)
        self.assertIn("x" * 500, preview)
        self.assertNotIn("x" * 501, preview)


class BannerConfigAdminDisplayTests(SimpleTestCase):
    def setUp(self):
        self.admin = sc_admin.BannerConfigAdmin(sc_models.BannerConfig, AdminSite())

    def test_statistics_are_readonly(self):
        for field in (
            "impressions",
            "dismissals",
            "necessary_only",
            "custom_saves",
            "accept_all",
        ):
            self.assertIn(field, self.admin.readonly_fields)
        self.assertIn("impressions", self.admin.list_display)


class ConsentRecordAdminDisplayTests(SimpleTestCase):
    def setUp(self):
        self.admin = sc_admin.ConsentRecordAdmin(sc_models.ConsentRecord, AdminSite())

    def test_no_write_permissions(self):
        request = type("R", (), {})()
        self.assertFalse(self.admin.has_add_permission(request))
        self.assertFalse(self.admin.has_change_permission(request))
        self.assertFalse(self.admin.has_delete_permission(request))

    def test_scripts_hash_short(self):
        short = sc_models.ConsentRecord(scripts_hash="abc")
        self.assertEqual(self.admin.scripts_hash_short(short), "abc")
        long = sc_models.ConsentRecord(scripts_hash="a" * 40)
        result = self.admin.scripts_hash_short(long)
        self.assertTrue(result.endswith("…"))
        self.assertEqual(result[:12], "a" * 12)
