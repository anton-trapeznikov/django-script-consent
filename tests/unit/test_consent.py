import uuid
from unittest.mock import patch

from django.test import SimpleTestCase

from script_consent.consent import (
    banner_template_context,
    build_consent_state,
    categories_for_banner,
    get_valid_consent,
    has_consent_gated_scripts,
    scripts_for_placement,
    should_show_banner,
)
from script_consent.cookies import ConsentState
from tests.helpers import make_consent_cookie, make_request, make_runtime


class GetValidConsentTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_valid_consent(self, mock_runtime):
        runtime = make_runtime(scripts_hash="h" * 64)
        mock_runtime.return_value = runtime
        cookie = make_consent_cookie(
            banner_id=runtime["banner"]["id"],
            banner_version=runtime["version"],
            scripts_hash=runtime["scripts_hash"],
        )
        request = make_request(cookies={"script_consent": cookie})
        consent = get_valid_consent(request)
        self.assertIsNotNone(consent)
        self.assertTrue(consent.valid)

    @patch("script_consent.consent.get_runtime_state")
    def test_no_banner_invalidates(self, mock_runtime):
        mock_runtime.return_value = make_runtime(banner=None, version=0)
        cookie = make_consent_cookie()
        request = make_request(cookies={"script_consent": cookie})
        self.assertIsNone(get_valid_consent(request))

    @patch("script_consent.consent.get_runtime_state")
    def test_banner_version_mismatch(self, mock_runtime):
        runtime = make_runtime(scripts_hash="h" * 64)
        mock_runtime.return_value = runtime
        cookie = make_consent_cookie(
            banner_id=runtime["banner"]["id"],
            banner_version=999,
            scripts_hash=runtime["scripts_hash"],
        )
        request = make_request(cookies={"script_consent": cookie})
        self.assertIsNone(get_valid_consent(request))

    @patch("script_consent.consent.get_runtime_state")
    def test_scripts_hash_mismatch(self, mock_runtime):
        runtime = make_runtime(scripts_hash="h" * 64)
        mock_runtime.return_value = runtime
        cookie = make_consent_cookie(
            banner_id=runtime["banner"]["id"],
            banner_version=runtime["version"],
            scripts_hash="deadbeef" * 8,
        )
        request = make_request(cookies={"script_consent": cookie})
        self.assertIsNone(get_valid_consent(request))

    @patch("script_consent.consent.get_runtime_state")
    def test_banner_id_mismatch(self, mock_runtime):
        runtime = make_runtime(scripts_hash="h" * 64)
        mock_runtime.return_value = runtime
        cookie = make_consent_cookie(
            banner_id=999,
            banner_version=runtime["version"],
            scripts_hash=runtime["scripts_hash"],
        )
        request = make_request(cookies={"script_consent": cookie})
        self.assertIsNone(get_valid_consent(request))

    def test_no_cookie(self):
        with patch(
            "script_consent.consent.get_runtime_state",
            return_value=make_runtime(),
        ):
            self.assertIsNone(get_valid_consent(make_request()))


class ShouldShowBannerTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_shown_when_gated_and_no_consent(self, mock_runtime):
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=True)
        request = make_request()
        self.assertTrue(should_show_banner(request, consent=None))

    @patch("script_consent.consent.get_runtime_state")
    def test_hidden_without_banner(self, mock_runtime):
        mock_runtime.return_value = make_runtime(
            banner=None, version=0, has_consent_gated_scripts=True
        )
        self.assertFalse(should_show_banner(make_request(), consent=None))

    @patch("script_consent.consent.get_runtime_state")
    def test_hidden_without_gated_scripts(self, mock_runtime):
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=False)
        self.assertFalse(should_show_banner(make_request(), consent=None))

    @patch("script_consent.consent.get_runtime_state")
    def test_hidden_with_valid_consent(self, mock_runtime):
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=True)
        consent = ConsentState(
            consent_id=uuid.uuid4(),
            categories=["technical"],
            banner_id=1,
            banner_version=1,
            scripts_hash="h" * 64,
            valid=True,
        )
        self.assertFalse(should_show_banner(make_request(), consent=consent))

    @patch("script_consent.consent.get_runtime_state")
    def test_hidden_when_dismissed(self, mock_runtime):
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=True)
        request = make_request(cookies={"script_banner_dismissed": "1"})
        self.assertFalse(should_show_banner(request, consent=None))


class ScriptsForPlacementTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_without_consent_only_required(self, mock_runtime):
        mock_runtime.return_value = make_runtime()
        head = scripts_for_placement(make_request(), "head", consent=None)
        body = scripts_for_placement(make_request(), "body_end", consent=None)
        self.assertEqual([s["name"] for s in head], ["Required"])
        self.assertEqual(body, [])

    @patch("script_consent.consent.get_runtime_state")
    def test_with_consent_includes_optional(self, mock_runtime):
        mock_runtime.return_value = make_runtime()
        consent = ConsentState(
            consent_id=uuid.uuid4(),
            categories=["technical", "analytics"],
            valid=True,
        )
        body = scripts_for_placement(make_request(), "body_end", consent=consent)
        self.assertEqual([s["name"] for s in body], ["Optional"])

    @patch("script_consent.consent.get_runtime_state")
    def test_always_load_without_consent(self, mock_runtime):
        runtime = make_runtime(
            scripts=[
                {
                    "id": 3,
                    "name": "Unconditional",
                    "category_id": 2,
                    "category_code": "analytics",
                    "is_required": False,
                    "always_load": True,
                    "requires_consent": False,
                    "placement": "body_end",
                    "code": "<!-- always -->",
                    "order": 0,
                },
                {
                    "id": 2,
                    "name": "Optional",
                    "category_id": 2,
                    "category_code": "analytics",
                    "is_required": False,
                    "always_load": False,
                    "requires_consent": True,
                    "placement": "body_end",
                    "code": "<!-- opt -->",
                    "order": 10,
                },
            ]
        )
        mock_runtime.return_value = runtime
        body = scripts_for_placement(make_request(), "body_end", consent=None)
        names = {s["name"] for s in body}
        self.assertIn("Unconditional", names)
        self.assertNotIn("Optional", names)


class CategoriesForBannerTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_includes_required_and_gated(self, mock_runtime):
        mock_runtime.return_value = make_runtime()
        cats = categories_for_banner()
        codes = {c["code"] for c in cats}
        self.assertIn("technical", codes)
        self.assertIn("analytics", codes)


class BuildConsentStateTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_builds_from_runtime(self, mock_runtime):
        runtime = make_runtime(scripts_hash="z" * 64)
        mock_runtime.return_value = runtime
        tech = type("C", (), {"code": "technical"})()
        state = build_consent_state(uuid.uuid4(), [tech])
        self.assertEqual(state.banner_id, runtime["banner"]["id"])
        self.assertEqual(state.banner_version, runtime["version"])
        self.assertEqual(state.scripts_hash, "z" * 64)
        self.assertEqual(state.categories, ["technical"])
        self.assertTrue(state.valid)

    @patch("script_consent.consent.get_runtime_state")
    def test_raises_without_banner(self, mock_runtime):
        mock_runtime.return_value = make_runtime(banner=None, version=0)
        with self.assertRaises(ValueError):
            build_consent_state(uuid.uuid4(), [])


class HasConsentGatedScriptsTests(SimpleTestCase):
    @patch("script_consent.consent.get_runtime_state")
    def test_flag(self, mock_runtime):
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=True)
        self.assertTrue(has_consent_gated_scripts())
        mock_runtime.return_value = make_runtime(has_consent_gated_scripts=False)
        self.assertFalse(has_consent_gated_scripts())


class BannerTemplateContextTests(SimpleTestCase):
    @patch("script_consent.consent.categories_for_banner")
    @patch("script_consent.consent.should_show_banner")
    @patch("script_consent.consent.get_runtime_state")
    def test_builds_banner_keys(self, mock_runtime, mock_show, mock_cats):
        runtime = make_runtime()
        mock_runtime.return_value = runtime
        mock_show.return_value = True
        mock_cats.return_value = runtime["categories"]
        request = make_request()

        ctx = banner_template_context(request, consent=None)

        self.assertTrue(ctx["show_consent_banner"])
        self.assertTrue(ctx["show_settings_button"])
        self.assertEqual(ctx["script_consent_banner"], runtime["banner"])
        self.assertEqual(ctx["script_consent_categories"], runtime["categories"])
        self.assertEqual(ctx["accepted_category_codes"], [])
        self.assertIs(ctx["request"], request)
        mock_show.assert_called_once_with(request, consent=None)

    @patch("script_consent.consent.should_show_banner", return_value=False)
    @patch("script_consent.consent.get_runtime_state")
    def test_overrides_skip_defaults(self, mock_runtime, _mock_show):
        request = make_request()
        custom_cats = [{"code": "only"}]
        ctx = banner_template_context(
            request,
            consent=None,
            categories=custom_cats,
            banner=None,
            privacy_url="/custom-privacy/",
        )
        # banner/categories/privacy taken from overrides — no runtime fetch for them
        mock_runtime.assert_not_called()
        self.assertEqual(ctx["script_consent_categories"], custom_cats)
        self.assertIsNone(ctx["script_consent_banner"])
        self.assertEqual(ctx["script_consent_privacy_url"], "/custom-privacy/")

    def test_without_request_no_auto_open(self):
        with patch("script_consent.consent.get_runtime_state") as mock_runtime:
            mock_runtime.return_value = make_runtime()
            with patch(
                "script_consent.consent.categories_for_banner",
                return_value=[],
            ):
                ctx = banner_template_context(None, consent=None)
        self.assertFalse(ctx["show_consent_banner"])
        self.assertIsNone(ctx["request"])
