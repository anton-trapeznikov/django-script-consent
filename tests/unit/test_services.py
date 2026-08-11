from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from script_consent.services import (
    resolve_accepted_categories,
    sanitize_privacy_policy_url,
)


class SanitizePrivacyPolicyUrlTests(SimpleTestCase):
    def test_relative_path(self):
        self.assertEqual(sanitize_privacy_policy_url("/privacy/"), "/privacy/")

    def test_https(self):
        self.assertEqual(
            sanitize_privacy_policy_url("https://example.com/p"),
            "https://example.com/p",
        )

    def test_http(self):
        self.assertEqual(
            sanitize_privacy_policy_url("http://example.com/p"),
            "http://example.com/p",
        )

    def test_blocks_javascript(self):
        self.assertIsNone(sanitize_privacy_policy_url("javascript:alert(1)"))

    def test_blocks_data(self):
        self.assertIsNone(sanitize_privacy_policy_url("data:text/html,hi"))

    def test_blocks_protocol_relative(self):
        self.assertIsNone(sanitize_privacy_policy_url("//evil.example/x"))

    def test_empty(self):
        self.assertIsNone(sanitize_privacy_policy_url(None))
        self.assertIsNone(sanitize_privacy_policy_url(""))
        self.assertIsNone(sanitize_privacy_policy_url("   "))


class ResolveAcceptedCategoriesTests(SimpleTestCase):
    @patch("script_consent.services.repositories.list_active_categories")
    def test_accept_all(self, list_active):
        tech = MagicMock(id=1, code="technical", order=0)
        analytics = MagicMock(id=2, code="analytics", order=10)
        list_active.return_value = [tech, analytics]

        result = resolve_accepted_categories("accept_all")

        self.assertEqual(result, [tech, analytics])
        list_active.assert_called_once_with()

    @patch("script_consent.services.repositories.list_required_categories")
    def test_reject_optional(self, list_required):
        tech = MagicMock(id=1, code="technical", order=0)
        list_required.return_value = [tech]

        result = resolve_accepted_categories("reject_optional")

        self.assertEqual(result, [tech])
        list_required.assert_called_once_with()

    @patch("script_consent.services.repositories.list_optional_categories_by_codes")
    @patch("script_consent.services.repositories.list_required_categories")
    def test_custom_merges_required(self, list_required, list_optional):
        tech = MagicMock(id=1, code="technical", order=0)
        marketing = MagicMock(id=3, code="marketing", order=20)
        list_required.return_value = [tech]
        list_optional.return_value = [marketing]

        result = resolve_accepted_categories("custom", ["marketing"])

        codes = {c.code for c in result}
        self.assertEqual(codes, {"technical", "marketing"})
        list_required.assert_called_once_with()
        list_optional.assert_called_once_with(["marketing"])

    @patch("script_consent.services.repositories.list_optional_categories_by_codes")
    @patch("script_consent.services.repositories.list_required_categories")
    def test_custom_preserves_order(self, list_required, list_optional):
        tech = MagicMock(id=1, code="technical", order=0)
        marketing = MagicMock(id=3, code="marketing", order=20)
        list_required.return_value = [tech]
        list_optional.return_value = [marketing]

        result = resolve_accepted_categories("custom", ["marketing"])

        self.assertEqual([c.code for c in result], ["technical", "marketing"])

    @patch("script_consent.services.repositories.list_active_categories")
    @patch("script_consent.services.repositories.list_required_categories")
    def test_withdraw_empty_without_orm(self, list_required, list_active):
        self.assertEqual(resolve_accepted_categories("withdraw"), [])
        list_active.assert_not_called()
        list_required.assert_not_called()

    def test_unknown_action(self):
        with self.assertRaises(ValueError):
            resolve_accepted_categories("unknown")
