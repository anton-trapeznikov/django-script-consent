import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from script_consent.models import (
    BannerConfig,
    ConsentRecord,
    RuntimeCacheStamp,
    ScriptCategory,
    ScriptSnippet,
)


def get_active_banner() -> BannerConfig | None:
    return BannerConfig.get_solo()


def list_active_categories() -> list[ScriptCategory]:
    return list(ScriptCategory.objects.filter(is_active=True).order_by("order", "id"))


def list_required_categories() -> list[ScriptCategory]:
    return list(
        ScriptCategory.objects.filter(is_active=True, is_required=True).order_by(
            "order", "id"
        )
    )


def list_optional_categories_by_codes(codes: Iterable[str]) -> list[ScriptCategory]:
    code_set = set(codes)
    if not code_set:
        return []
    return list(
        ScriptCategory.objects.filter(
            is_active=True, is_required=False, code__in=code_set
        ).order_by("order", "id")
    )


def list_active_scripts() -> list[ScriptSnippet]:
    return list(
        ScriptSnippet.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .order_by("order", "id")
    )


def create_consent_record(
    *,
    consent_id: uuid.UUID,
    user: Any | None,
    ip_address: str | None,
    user_agent: str,
    action: str,
    banner_version: int,
    scripts_hash: str,
    categories: Iterable[ScriptCategory],
) -> ConsentRecord:
    record = ConsentRecord.objects.create(
        consent_id=consent_id,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        action=action,
        banner_version=banner_version,
        scripts_hash=scripts_hash,
    )
    record.accepted_categories.set(categories)
    return record


def cache_stamp_current() -> int:
    return RuntimeCacheStamp.current()


def cache_stamp_bump() -> int:
    return RuntimeCacheStamp.bump()


def purge_consent_records_before(cutoff: datetime) -> tuple[int, dict]:
    return ConsentRecord.objects.filter(created_at__lt=cutoff).delete()


def count_consent_records_before(cutoff: datetime) -> int:
    return ConsentRecord.objects.filter(created_at__lt=cutoff).count()
