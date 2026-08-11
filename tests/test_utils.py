import json
import uuid

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet
from script_consent.utils import (
    anonymize_ip,
    build_consent_state,
    compute_scripts_hash,
    compute_scripts_hash_from_rows,
    decode_consent_payload,
    encode_consent_payload,
    get_client_ip,
    get_runtime_state,
    get_valid_consent,
    invalidate_runtime_cache,
    is_dismissed,
    resolve_accepted_categories,
    script_row_requires_consent,
    scripts_for_placement,
    should_show_banner,
)


class HashTests(TestCase):
    def setUp(self):
        cache.clear()
        ScriptSnippet.objects.all().delete()
        self.cat = ScriptCategory.objects.get(code="analytics")
        self.tech = ScriptCategory.objects.get(code="technical")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        BannerConfig.objects.create(title="B", text="t", version=1, is_active=True)

    def test_hash_stable_for_same_scripts(self):
        ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            placement="body_end",
            code="<script>1</script>",
            order=1,
        )
        h1 = compute_scripts_hash()
        invalidate_runtime_cache()
        h2 = compute_scripts_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_hash_changes_on_code_change(self):
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

    def test_hash_changes_on_deactivate(self):
        s = ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
            is_active=True,
        )
        h1 = compute_scripts_hash()
        s.is_active = False
        s.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_category_reassign(self):
        s = ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
        )
        h1 = compute_scripts_hash()
        s.category = self.tech
        s.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_always_load_toggle(self):
        s = ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
            always_load=False,
        )
        h1 = compute_scripts_hash()
        s.always_load = True
        s.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_is_required_toggle(self):
        ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
        )
        h1 = compute_scripts_hash()
        self.cat.is_required = True
        self.cat.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)
        # Load policy must change: optional script becomes unconditional
        request = RequestFactory().get("/")
        request.COOKIES = {}
        body = scripts_for_placement(request, "body_end")
        self.assertTrue(any(s["name"] == "S1" for s in body))

    def test_hash_changes_on_category_title_change(self):
        ScriptSnippet.objects.create(
            name="S1",
            category=self.cat,
            code="<script>1</script>",
        )
        h1 = compute_scripts_hash()
        self.cat.title = "Analytics (updated purpose)"
        self.cat.save()
        h2 = compute_scripts_hash()
        self.assertNotEqual(h1, h2)

    def test_from_rows_empty(self):
        self.assertEqual(
            compute_scripts_hash_from_rows([]),
            compute_scripts_hash_from_rows([]),
        )


class CookiePayloadTests(TestCase):
    def test_encode_decode_roundtrip(self):
        payload = {
            "v": 1,
            "consent_id": str(uuid.uuid4()),
            "categories": ["technical", "analytics"],
            "banner_id": 7,
            "banner_version": 2,
            "scripts_hash": "abc",
        }
        encoded = encode_consent_payload(payload)
        decoded = decode_consent_payload(encoded)
        self.assertEqual(decoded["consent_id"], payload["consent_id"])
        self.assertEqual(decoded["categories"], payload["categories"])
        self.assertEqual(decoded["banner_id"], 7)
        self.assertEqual(decoded["banner_version"], 2)

    def test_invalid_payload(self):
        self.assertIsNone(decode_consent_payload("not-valid"))
        self.assertIsNone(decode_consent_payload(""))


class ConsentValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        ScriptSnippet.objects.all().delete()
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        self.banner = BannerConfig.objects.create(
            title="B", text="t", version=1, is_active=True
        )
        ScriptSnippet.objects.create(
            name="Required",
            category=self.tech,
            placement="head",
            code="<!-- req -->",
        )
        ScriptSnippet.objects.create(
            name="Optional",
            category=self.analytics,
            placement="body_end",
            code="<!-- opt -->",
        )

    def _request_with_consent(self, **overrides):
        state = build_consent_state(
            uuid.uuid4(),
            [self.tech, self.analytics],
        )
        data = state.to_dict()
        data.update(overrides)
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(data),
        }
        return request

    def test_valid_consent(self):
        request = self._request_with_consent()
        consent = get_valid_consent(request)
        self.assertIsNotNone(consent)
        self.assertTrue(consent.valid)
        self.assertFalse(should_show_banner(request))

    def test_invalid_on_banner_version_mismatch(self):
        request = self._request_with_consent(banner_version=999)
        self.assertIsNone(get_valid_consent(request))
        self.assertTrue(should_show_banner(request))

    def test_invalid_on_scripts_hash_mismatch(self):
        request = self._request_with_consent(scripts_hash="deadbeef" * 8)
        self.assertIsNone(get_valid_consent(request))

    def test_dismiss_hides_banner_without_consent(self):
        request = self.factory.get("/")
        request.COOKIES = {"script_banner_dismissed": "1"}
        self.assertTrue(is_dismissed(request))
        self.assertFalse(should_show_banner(request))

    def test_scripts_without_consent_only_required(self):
        request = self.factory.get("/")
        request.COOKIES = {}
        head = scripts_for_placement(request, "head")
        body = scripts_for_placement(request, "body_end")
        self.assertEqual(len(head), 1)
        self.assertEqual(head[0]["name"], "Required")
        self.assertEqual(body, [])

    def test_scripts_with_consent_include_optional(self):
        request = self._request_with_consent()
        body = scripts_for_placement(request, "body_end")
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "Optional")

    def test_always_load_without_consent(self):
        ScriptSnippet.objects.create(
            name="Unconditional",
            category=self.analytics,
            placement="body_end",
            code="<!-- always -->",
            always_load=True,
        )
        request = self.factory.get("/")
        request.COOKIES = {}
        body = scripts_for_placement(request, "body_end")
        names = {s["name"] for s in body}
        self.assertIn("Unconditional", names)
        self.assertNotIn("Optional", names)

    def test_banner_hidden_when_no_consent_gated_scripts(self):
        ScriptSnippet.objects.all().delete()
        # only required category + always_load optional
        ScriptSnippet.objects.create(
            name="Req",
            category=self.tech,
            placement="head",
            code="<!-- r -->",
        )
        ScriptSnippet.objects.create(
            name="Always",
            category=self.analytics,
            placement="body_end",
            code="<!-- a -->",
            always_load=True,
        )
        request = self.factory.get("/")
        request.COOKIES = {}
        self.assertFalse(should_show_banner(request))

    def test_banner_hidden_when_no_scripts_at_all(self):
        ScriptSnippet.objects.all().delete()
        request = self.factory.get("/")
        request.COOKIES = {}
        self.assertFalse(should_show_banner(request))

    def test_banner_shown_when_consent_gated_script_exists(self):
        request = self.factory.get("/")
        request.COOKIES = {}
        # setUp has optional analytics script without always_load
        self.assertTrue(should_show_banner(request))


class ResolveCategoriesTests(TestCase):
    def setUp(self):
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        self.marketing = ScriptCategory.objects.get(code="marketing")

    def test_accept_all(self):
        cats = resolve_accepted_categories("accept_all")
        self.assertEqual(
            {c.code for c in cats}, {"technical", "analytics", "marketing"}
        )

    def test_reject_optional(self):
        cats = resolve_accepted_categories("reject_optional")
        self.assertEqual([c.code for c in cats], ["technical"])

    def test_custom_always_includes_required(self):
        cats = resolve_accepted_categories("custom", ["marketing"])
        codes = {c.code for c in cats}
        self.assertIn("technical", codes)
        self.assertIn("marketing", codes)
        self.assertNotIn("analytics", codes)

    def test_withdraw_empty(self):
        self.assertEqual(resolve_accepted_categories("withdraw"), [])

    def test_resolve_unknown_action(self):
        with self.assertRaises(ValueError):
            resolve_accepted_categories("unknown")


class AnonymizeIpTests(TestCase):
    def test_ipv4(self):
        self.assertEqual(anonymize_ip("203.0.113.45"), "203.0.113.0")

    def test_ipv6(self):
        result = anonymize_ip("2001:db8:85a3::8a2e:370:7334")
        self.assertTrue(result.startswith("2001:db8:85a3:"))
        # lower 80 bits zeroed
        self.assertEqual(result, "2001:db8:85a3::")

    @override_settings(SCRIPT_CONSENT={"ANONYMIZE_IP": False})
    def test_disabled(self):
        # conf reads settings at getattr time; app_settings uses getattr each time
        self.assertEqual(anonymize_ip("203.0.113.45"), "203.0.113.45")

    def test_invalid_ip(self):
        self.assertIsNone(anonymize_ip("not-an-ip"))
        self.assertIsNone(anonymize_ip(""))

    def test_cookie_secure_from_session(self):
        from django.conf import settings as dj_settings

        original = getattr(dj_settings, "SESSION_COOKIE_SECURE", False)
        dj_settings.SESSION_COOKIE_SECURE = True
        try:
            from script_consent.utils import _cookie_secure

            self.assertTrue(_cookie_secure())
        finally:
            dj_settings.SESSION_COOKIE_SECURE = original

    def test_dismiss_max_age_explicit(self):
        from script_consent.utils import dismiss_max_age_seconds

        with override_settings(SCRIPT_CONSENT={"DISMISS_MAX_AGE": 3600}):
            self.assertEqual(dismiss_max_age_seconds(), 3600)

    def test_get_client_ip_ignores_xff_by_default(self):
        factory = RequestFactory()
        request = factory.get(
            "/",
            REMOTE_ADDR="198.51.100.9",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        self.assertEqual(get_client_ip(request), "198.51.100.0")

    @override_settings(
        SCRIPT_CONSENT={"TRUST_X_FORWARDED_FOR": True, "ANONYMIZE_IP": True}
    )
    def test_get_client_ip_uses_x_forwarded_for_when_trusted(self):
        factory = RequestFactory()
        request = factory.get(
            "/",
            REMOTE_ADDR="198.51.100.9",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        self.assertEqual(get_client_ip(request), "203.0.113.0")

    def test_get_client_ip_falls_back_to_remote_addr(self):
        factory = RequestFactory()
        request = factory.get("/", REMOTE_ADDR="203.0.113.45")
        self.assertEqual(get_client_ip(request), "203.0.113.0")


class ScriptRowRequiresConsentTests(TestCase):
    def test_explicit_requires_consent(self):
        self.assertTrue(script_row_requires_consent({"requires_consent": True}))
        self.assertFalse(script_row_requires_consent({"requires_consent": False}))

    def test_always_load_false(self):
        self.assertFalse(
            script_row_requires_consent({"always_load": True, "is_required": False})
        )

    def test_required_category(self):
        self.assertFalse(
            script_row_requires_consent({"always_load": False, "is_required": True})
        )

    def test_optional_category(self):
        self.assertTrue(
            script_row_requires_consent({"always_load": False, "is_required": False})
        )


class DecodeConsentPayloadTests(TestCase):
    def test_decode_dict_raw(self):
        payload = {"consent_id": str(uuid.uuid4()), "categories": []}
        encoded = encode_consent_payload(payload)
        decoded = decode_consent_payload(encoded)
        self.assertEqual(decoded["consent_id"], payload["consent_id"])

    def test_decode_with_unsigned_cookie(self):
        payload = {"consent_id": str(uuid.uuid4()), "categories": ["analytics"]}
        raw = json.dumps(payload)
        with override_settings(SCRIPT_CONSENT={"SIGNED_COOKIE": False}):
            decoded = decode_consent_payload(raw)
        self.assertEqual(decoded["consent_id"], payload["consent_id"])

    def test_decode_returns_none_for_non_dict(self):
        with override_settings(SCRIPT_CONSENT={"SIGNED_COOKIE": False}):
            self.assertIsNone(decode_consent_payload('"string"'))
            self.assertIsNone(decode_consent_payload("123"))

    def test_encode_unsigned_cookie(self):
        payload = {"consent_id": str(uuid.uuid4()), "categories": []}
        with override_settings(SCRIPT_CONSENT={"SIGNED_COOKIE": False}):
            encoded = encode_consent_payload(payload)
        self.assertIn("consent_id", encoded)


class GetValidConsentEdgeCasesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        ScriptSnippet.objects.all().delete()
        self.tech = ScriptCategory.objects.get(code="technical")
        self.analytics = ScriptCategory.objects.get(code="analytics")
        BannerConfig.objects.filter(is_active=True).update(is_active=False)
        self.banner = BannerConfig.objects.create(
            title="B", text="t", version=1, is_active=True
        )
        ScriptSnippet.objects.create(
            name="Required",
            category=self.tech,
            placement="head",
            code="<!-- req -->",
        )
        ScriptSnippet.objects.create(
            name="Optional",
            category=self.analytics,
            placement="body_end",
            code="<!-- opt -->",
        )

    def test_invalid_consent_id(self):
        runtime = get_runtime_state()
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(
                {
                    "consent_id": "not-a-uuid",
                    "categories": [],
                    "banner_id": runtime["banner"]["id"],
                    "banner_version": 1,
                    "scripts_hash": runtime["scripts_hash"],
                }
            ),
        }
        self.assertIsNone(get_valid_consent(request))

    def test_invalid_banner_version_type(self):
        runtime = get_runtime_state()
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(
                {
                    "consent_id": str(uuid.uuid4()),
                    "categories": [],
                    "banner_id": runtime["banner"]["id"],
                    "banner_version": "not-int",
                    "scripts_hash": runtime["scripts_hash"],
                }
            ),
        }
        self.assertIsNone(get_valid_consent(request))

    def test_invalid_when_banner_id_missing(self):
        runtime = get_runtime_state()
        request = self.factory.get("/")
        request.COOKIES = {
            "script_consent": encode_consent_payload(
                {
                    "consent_id": str(uuid.uuid4()),
                    "categories": ["technical", "analytics"],
                    "banner_version": runtime["version"],
                    "scripts_hash": runtime["scripts_hash"],
                }
            ),
        }
        self.assertIsNone(get_valid_consent(request))

    def test_invalid_on_banner_switch_same_version(self):
        """Activating another BannerConfig invalidates consent even if both at v1."""
        state = build_consent_state(uuid.uuid4(), [self.tech, self.analytics])
        request = self.factory.get("/")
        request.COOKIES = {"script_consent": encode_consent_payload(state.to_dict())}
        self.assertIsNotNone(get_valid_consent(request))

        BannerConfig.objects.create(
            title="Other", text="different text", version=1, is_active=True
        )
        self.assertIsNone(get_valid_consent(request))

    def test_is_required_flip_invalidates_prior_consent(self):
        state = build_consent_state(uuid.uuid4(), [self.tech])  # necessary only
        request = self.factory.get("/")
        request.COOKIES = {"script_consent": encode_consent_payload(state.to_dict())}
        self.assertIsNotNone(get_valid_consent(request))

        self.analytics.is_required = True
        self.analytics.save()
        self.assertIsNone(get_valid_consent(request))
