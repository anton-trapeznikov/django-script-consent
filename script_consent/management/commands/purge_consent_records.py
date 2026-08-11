from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from script_consent import repositories
from script_consent.conf import app_settings


class Command(BaseCommand):
    help = (
        "Delete cookie consent audit records older than N days. "
        "Uses SCRIPT_CONSENT['CONSENT_RECORD_RETENTION_DAYS'] when --days is omitted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Delete records older than this many days (overrides settings).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count matching rows without deleting.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = app_settings.CONSENT_RECORD_RETENTION_DAYS
        if days is None:
            raise CommandError(
                "Retention is not configured. Pass --days N or set "
                "SCRIPT_CONSENT['CONSENT_RECORD_RETENTION_DAYS']."
            )
        if days < 1:
            raise CommandError("--days must be a positive integer.")

        cutoff = timezone.now() - timedelta(days=days)
        if options["dry_run"]:
            count = repositories.count_consent_records_before(cutoff)
            self.stdout.write(
                self.style.WARNING(
                    f"Would delete {count} consent record(s) older than {days} day(s) "
                    f"(before {cutoff.isoformat()})."
                )
            )
            return

        deleted, _ = repositories.purge_consent_records_before(cutoff)
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} consent record(s) older than {days} day(s)."
            )
        )
