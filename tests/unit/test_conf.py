from unittest import mock

from django.test import SimpleTestCase, override_settings

from script_consent.conf import DEFAULTS, ScriptConsentSettings, app_settings


class ScriptConsentSettingsTests(SimpleTestCase):
    def test_user_override(self):
        for key in DEFAULTS:
            override = {key: mock.Mock()}
            with (
                self.subTest(key=key),
                override_settings(SCRIPT_CONSENT=override),
            ):
                settings = ScriptConsentSettings()
                self.assertEqual(getattr(settings, key), override[key])

    def test_unknown_setting(self):
        with self.assertRaises(AttributeError):
            _ = app_settings.UNKNOWN_SETTING

    def test_as_dict_contains_all_defaults(self):
        d = app_settings.as_dict()
        for key in DEFAULTS:
            with self.subTest(key=key):
                self.assertIn(key, d)
                self.assertEqual(d[key], DEFAULTS[key])
