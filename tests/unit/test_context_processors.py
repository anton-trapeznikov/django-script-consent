from unittest.mock import patch

from django.test import SimpleTestCase

from script_consent.context_processors import script_consent
from tests.helpers import make_request, make_runtime


class ScriptConsentContextProcessorTests(SimpleTestCase):
    @patch("script_consent.context_processors.get_runtime_state")
    @patch("script_consent.context_processors.consent.scripts_for_placement")
    @patch("script_consent.context_processors.consent.banner_template_context")
    @patch("script_consent.context_processors.consent.get_valid_consent")
    def test_builds_context(
        self,
        mock_get_valid,
        mock_banner_ctx,
        mock_placement,
        mock_runtime,
    ):
        runtime = make_runtime(scripts_hash="abc")
        mock_runtime.return_value = runtime
        mock_get_valid.return_value = None
        mock_banner_ctx.return_value = {
            "show_consent_banner": True,
            "script_consent_banner": runtime["banner"],
            "script_consent_privacy_url": "/privacy/",
        }
        mock_placement.return_value = []

        request = make_request()
        ctx = script_consent(request)

        self.assertTrue(ctx["show_consent_banner"])
        self.assertIsNone(ctx["current_consent"])
        self.assertEqual(ctx["script_consent_banner"], runtime["banner"])
        self.assertEqual(ctx["script_consent_scripts_hash"], "abc")
        self.assertEqual(ctx["script_consent_privacy_url"], "/privacy/")
        mock_banner_ctx.assert_called_once_with(request, consent=None)
        self.assertEqual(mock_placement.call_count, 3)
