from django.test import SimpleTestCase, override_settings

from script_consent.ip import anonymize_ip, get_client_ip
from tests.helpers import make_request


class AnonymizeIpTests(SimpleTestCase):
    def test_ipv4(self):
        self.assertEqual(anonymize_ip("203.0.113.45"), "203.0.113.0")

    def test_ipv6(self):
        result = anonymize_ip("2001:db8:85a3::8a2e:370:7334")
        self.assertEqual(result, "2001:db8:85a3::")

    @override_settings(SCRIPT_CONSENT={"ANONYMIZE_IP": False})
    def test_disabled(self):
        self.assertEqual(anonymize_ip("203.0.113.45"), "203.0.113.45")

    def test_invalid_ip(self):
        self.assertIsNone(anonymize_ip("not-an-ip"))
        self.assertIsNone(anonymize_ip(""))
        self.assertIsNone(anonymize_ip(None))


class GetClientIpTests(SimpleTestCase):
    def test_ignores_xff_by_default(self):
        request = make_request(
            REMOTE_ADDR="198.51.100.9",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        self.assertEqual(get_client_ip(request), "198.51.100.0")

    @override_settings(
        SCRIPT_CONSENT={"TRUST_X_FORWARDED_FOR": True, "ANONYMIZE_IP": True}
    )
    def test_uses_xff_when_trusted(self):
        request = make_request(
            REMOTE_ADDR="198.51.100.9",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        self.assertEqual(get_client_ip(request), "203.0.113.0")

    def test_falls_back_to_remote_addr(self):
        request = make_request(REMOTE_ADDR="203.0.113.45")
        self.assertEqual(get_client_ip(request), "203.0.113.0")
