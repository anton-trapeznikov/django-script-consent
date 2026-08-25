import contextlib
from typing import Any

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError

from script_consent import repositories
from script_consent.conf import app_settings
from script_consent.hashing import compute_scripts_hash_from_rows


def _cache_generation() -> int:
    try:
        return repositories.cache_stamp_current()
    except (OperationalError, ProgrammingError):
        return 0


def _cache_key() -> str:
    return f"{app_settings.CACHE_KEY}:v{_cache_generation()}"


def invalidate_runtime_cache() -> None:
    old_key = _cache_key()

    with contextlib.suppress(OperationalError, ProgrammingError):
        repositories.cache_stamp_bump()

    with contextlib.suppress(Exception):
        cache.delete(old_key)

    with contextlib.suppress(Exception):
        cache.delete(app_settings.CACHE_KEY)


def _category_row(c) -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "title": c.title,
        "description": c.description,
        "is_required": c.is_required,
        "order": c.order,
        "is_active": c.is_active,
    }


def _script_row(s) -> dict[str, Any]:
    always_load = bool(s.always_load)
    is_required_cat = bool(s.category.is_required)
    requires_consent = (not always_load) and (not is_required_cat)

    return {
        "id": s.id,
        "name": s.name,
        "category_id": s.category_id,
        "category_code": s.category.code,
        "is_required": is_required_cat,
        "always_load": always_load,
        "requires_consent": requires_consent,
        "placement": s.placement,
        "code": s.code,
        "order": s.order,
        "recipient": s.recipient or "",
    }


def _banner_payload(banner) -> tuple[dict[str, Any] | None, int]:
    if banner is None:
        return None, 0

    return (
        {
            "id": banner.id,
            "title": banner.title,
            "text": banner.text,
            "operator": banner.operator or "",
            "privacy_url": banner.privacy_url or "",
            "version": banner.version,
            "is_active": banner.is_active,
        },
        banner.version,
    )


def get_runtime_state() -> dict[str, Any]:
    key = _cache_key()
    data = cache.get(key)

    if data is not None:
        return data

    categories = [_category_row(c) for c in repositories.list_active_categories()]
    scripts = [_script_row(s) for s in repositories.list_active_scripts()]
    banner_payload, version = _banner_payload(repositories.get_active_banner())
    scripts_hash = compute_scripts_hash_from_rows(scripts, categories)

    data = {
        "banner": banner_payload,
        "version": version,
        "scripts_hash": scripts_hash,
        "scripts": scripts,
        "categories": categories,
        "has_consent_gated_scripts": any(s["requires_consent"] for s in scripts),
    }

    cache.set(key, data, app_settings.CACHE_TIMEOUT)
    return data


def compute_scripts_hash() -> str:
    return get_runtime_state()["scripts_hash"]
