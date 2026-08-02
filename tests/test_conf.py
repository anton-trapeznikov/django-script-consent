from django.test import TestCase, override_settings

from script_consent.conf import ScriptConsentSettings, app_settings


class ScriptConsentSettingsTests(TestCase):
    def test_default_value(self):
        self.assertEqual(app_settings.CONSENT_COOKIE, "script_consent")

    @override_settings(SCRIPT_CONSENT={"CONSENT_COOKIE": "custom_consent"})
    def test_user_override(self):
        settings = ScriptConsentSettings()
        self.assertEqual(settings.CONSENT_COOKIE, "custom_consent")

    def test_unknown_setting_raises(self):
        with self.assertRaises(AttributeError):
            _ = app_settings.UNKNOWN_SETTING

    def test_as_dict_contains_all_defaults(self):
        d = app_settings.as_dict()
        self.assertIn("CONSENT_COOKIE", d)
        self.assertIn("MAX_AGE", d)
        self.assertEqual(d["CONSENT_COOKIE"], "script_consent")
        self.assertTrue(d["COOKIE_HTTPONLY"])
        self.assertFalse(d["TRUST_X_FORWARDED_FOR"])
        self.assertFalse(d["SET_CONSENT_ID_COOKIE"])
