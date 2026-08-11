import uuid

from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings

from script_consent.cookies import (
    ConsentState,
    _cookie_secure,
    clear_consent_cookies,
    clear_dismiss_cookie,
    decode_consent_payload,
    dismiss_max_age_seconds,
    encode_consent_payload,
    get_consent_from_request,
    is_dismissed,
    set_consent_cookies,
    set_dismiss_cookie,
)
from tests.helpers import make_request


class EncodeDecodeTests(SimpleTestCase):
    def test_roundtrip_signed(self):
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

    @override_settings(SCRIPT_CONSENT={"SIGNED_COOKIE": False})
    def test_unsigned_roundtrip(self):
        payload = {"consent_id": str(uuid.uuid4()), "categories": ["analytics"]}
        encoded = encode_consent_payload(payload)
        self.assertIn("consent_id", encoded)
        decoded = decode_consent_payload(encoded)
        self.assertEqual(decoded["consent_id"], payload["consent_id"])

    @override_settings(SCRIPT_CONSENT={"SIGNED_COOKIE": False})
    def test_non_dict_json_returns_none(self):
        self.assertIsNone(decode_consent_payload('"string"'))
        self.assertIsNone(decode_consent_payload("123"))


class ConsentStateTests(SimpleTestCase):
    def test_to_dict(self):
        cid = uuid.uuid4()
        state = ConsentState(
            consent_id=cid,
            categories=["technical"],
            banner_id=3,
            banner_version=2,
            scripts_hash="h" * 64,
            valid=True,
        )
        data = state.to_dict()
        self.assertEqual(data["v"], 1)
        self.assertEqual(data["consent_id"], str(cid))
        self.assertEqual(data["categories"], ["technical"])
        self.assertEqual(data["banner_id"], 3)
        self.assertEqual(data["banner_version"], 2)
        self.assertEqual(data["scripts_hash"], "h" * 64)


class GetConsentFromRequestTests(SimpleTestCase):
    def test_parses_valid_cookie(self):
        cid = uuid.uuid4()
        payload = encode_consent_payload(
            {
                "consent_id": str(cid),
                "categories": ["technical"],
                "banner_id": 1,
                "banner_version": 2,
                "scripts_hash": "x" * 64,
            }
        )
        request = make_request(cookies={"script_consent": payload})
        state = get_consent_from_request(request)
        self.assertIsNotNone(state)
        self.assertEqual(state.consent_id, cid)
        self.assertEqual(state.banner_id, 1)
        self.assertFalse(state.valid)

    def test_missing_banner_id(self):
        payload = encode_consent_payload(
            {
                "consent_id": str(uuid.uuid4()),
                "categories": [],
                "banner_version": 1,
                "scripts_hash": "x" * 64,
            }
        )
        request = make_request(cookies={"script_consent": payload})
        self.assertIsNone(get_consent_from_request(request))

    def test_invalid_consent_id(self):
        payload = encode_consent_payload(
            {
                "consent_id": "not-a-uuid",
                "categories": [],
                "banner_id": 1,
                "banner_version": 1,
                "scripts_hash": "x" * 64,
            }
        )
        request = make_request(cookies={"script_consent": payload})
        self.assertIsNone(get_consent_from_request(request))

    def test_no_cookie(self):
        self.assertIsNone(get_consent_from_request(make_request()))


class CookieSetClearTests(SimpleTestCase):
    def test_set_and_clear_consent_cookies(self):
        response = HttpResponse()
        state = ConsentState(
            consent_id=uuid.uuid4(),
            categories=["technical"],
            banner_id=1,
            banner_version=1,
            scripts_hash="h" * 64,
        )
        set_consent_cookies(response, state)
        self.assertIn("script_consent", response.cookies)
        clear_consent_cookies(response)
        # delete_cookie sets max-age 0
        self.assertIn(response.cookies["script_consent"]["max-age"], (0, "0"))

    def test_dismiss_cookie_helpers(self):
        response = HttpResponse()
        set_dismiss_cookie(response)
        self.assertIn("script_banner_dismissed", response.cookies)
        clear_dismiss_cookie(response)
        self.assertIn(response.cookies["script_banner_dismissed"]["max-age"], (0, "0"))

    def test_is_dismissed(self):
        self.assertTrue(
            is_dismissed(make_request(cookies={"script_banner_dismissed": "1"}))
        )
        self.assertFalse(is_dismissed(make_request()))

    @override_settings(SCRIPT_CONSENT={"DISMISS_MAX_AGE": 3600})
    def test_dismiss_max_age_explicit(self):
        self.assertEqual(dismiss_max_age_seconds(), 3600)

    def test_cookie_secure_explicit(self):
        with override_settings(SCRIPT_CONSENT={"COOKIE_SECURE": True}):
            self.assertTrue(_cookie_secure())
        with override_settings(SCRIPT_CONSENT={"COOKIE_SECURE": False}):
            self.assertFalse(_cookie_secure())
