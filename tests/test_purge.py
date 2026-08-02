from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from script_consent.models import ConsentRecord


class PurgeConsentRecordsTests(TestCase):
    def setUp(self):
        ConsentRecord.objects.all().delete()
        self.old = ConsentRecord.objects.create(
            action=ConsentRecord.Action.ACCEPT_ALL,
            banner_version=1,
            scripts_hash="a" * 64,
        )
        ConsentRecord.objects.filter(pk=self.old.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        self.recent = ConsentRecord.objects.create(
            action=ConsentRecord.Action.ACCEPT_ALL,
            banner_version=1,
            scripts_hash="b" * 64,
        )

    def test_requires_days_or_setting(self):
        with self.assertRaises(CommandError):
            call_command("purge_consent_records")

    def test_dry_run_does_not_delete(self):
        out = StringIO()
        call_command("purge_consent_records", days=30, dry_run=True, stdout=out)
        self.assertEqual(ConsentRecord.objects.count(), 2)
        self.assertIn("Would delete", out.getvalue())

    def test_deletes_old_records(self):
        call_command("purge_consent_records", days=30)
        self.assertEqual(ConsentRecord.objects.count(), 1)
        self.assertEqual(ConsentRecord.objects.get().pk, self.recent.pk)

    @override_settings(SCRIPT_CONSENT={"CONSENT_RECORD_RETENTION_DAYS": 30})
    def test_uses_setting_when_days_omitted(self):
        call_command("purge_consent_records")
        self.assertEqual(ConsentRecord.objects.count(), 1)
