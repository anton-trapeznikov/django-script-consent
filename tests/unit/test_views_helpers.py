import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from script_consent.views import _json_body, accept_consent
from tests.helpers import make_request


class JsonBodyTests(SimpleTestCase):
    def test_empty(self):
        request = make_request()
        request._body = b""
        # RequestFactory GET has empty body
        self.assertEqual(_json_body(request), {})

    def test_valid_dict(self):
        request = make_request()
        request._body = json.dumps({"action": "accept_all"}).encode()
        self.assertEqual(_json_body(request)["action"], "accept_all")

    def test_invalid_json(self):
        request = make_request()
        request._body = b"not-json"
        self.assertEqual(_json_body(request), {})

    def test_non_dict(self):
        request = make_request()
        request._body = b'"string"'
        self.assertEqual(_json_body(request), {})


class AcceptConsentGuardTests(SimpleTestCase):
    @patch("script_consent.views.get_runtime_state")
    def test_no_active_banner(self, mock_runtime):
        mock_runtime.return_value = {
            "banner": None,
            "version": 0,
            "scripts_hash": "h" * 64,
            "scripts": [],
            "categories": [],
            "has_consent_gated_scripts": False,
        }
        request = make_request()
        request.method = "POST"
        request._body = json.dumps({"action": "accept_all"}).encode()
        request.user = MagicMock(is_authenticated=False)

        response = accept_consent(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"ok": False, "error": "no_active_banner"},
        )

    @patch("script_consent.views.get_runtime_state")
    def test_invalid_action(self, mock_runtime):
        mock_runtime.return_value = {"banner": {"id": 1}}
        request = make_request()
        request.method = "POST"
        request._body = json.dumps({"action": "nope"}).encode()
        request.user = MagicMock(is_authenticated=False)

        response = accept_consent(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content)["error"],
            "invalid_action",
        )
