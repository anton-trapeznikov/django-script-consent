"""scripts_hash, cookies, consent validation, IP anonymization, runtime cache."""

from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from django.core import signing
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from script_consent.conf import app_settings

# Sentinel for optional consent kwarg (avoid re-fetch when caller already has it)
_UNSET: Any = object()

# ---------------------------------------------------------------------------
# Runtime cache
# ---------------------------------------------------------------------------


def _cache_generation() -> int:
    """DB-backed generation so LocMem multi-process caches converge on invalidate."""
    try:
        from script_consent.models import RuntimeCacheStamp

        return RuntimeCacheStamp.current()
    except (OperationalError, ProgrammingError, ImportError):
        return 0


def _cache_key() -> str:
    return f"{app_settings.CACHE_KEY}:v{_cache_generation()}"


def invalidate_runtime_cache() -> None:
    """
    Bump the DB generation counter so every process misses the old cache key.
    Also deletes the key that was current before the bump.
    """
    old_key = _cache_key()
    try:
        from script_consent.models import RuntimeCacheStamp

        RuntimeCacheStamp.bump()
    except (OperationalError, ProgrammingError, ImportError):
        pass
    with contextlib.suppress(Exception):
        cache.delete(old_key)
    # Legacy unversioned key (pre-0.1.1)
    with contextlib.suppress(Exception):
        cache.delete(app_settings.CACHE_KEY)


def get_runtime_state() -> dict[str, Any]:
    """
    Cached snapshot: banner, version, scripts_hash, scripts, categories.
    """
    key = _cache_key()
    data = cache.get(key)
    if data is not None:
        return data

    from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet

    banner = BannerConfig.get_solo()
    categories_qs = ScriptCategory.objects.filter(is_active=True).order_by(
        "order", "id"
    )
    categories = [
        {
            "id": c.id,
            "code": c.code,
            "title": c.title,
            "description": c.description,
            "is_required": c.is_required,
            "order": c.order,
            "is_active": c.is_active,
        }
        for c in categories_qs
    ]

    scripts_qs = (
        ScriptSnippet.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .order_by("order", "id")
    )
    scripts = []
    for s in scripts_qs:
        always_load = bool(s.always_load)
        is_required_cat = bool(s.category.is_required)
        # Consent is needed only for non-required categories without always_load
        requires_consent = (not always_load) and (not is_required_cat)
        scripts.append(
            {
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
            }
        )

    scripts_hash = compute_scripts_hash_from_rows(scripts, categories)
    has_consent_gated_scripts = any(s["requires_consent"] for s in scripts)

    data = {
        "banner": {
            "id": banner.id,
            "title": banner.title,
            "text": banner.text,
            "version": banner.version,
            "is_active": banner.is_active,
        },
        "version": banner.version,
        "scripts_hash": scripts_hash,
        "scripts": scripts,
        "categories": categories,
        "has_consent_gated_scripts": has_consent_gated_scripts,
    }
    cache.set(key, data, app_settings.CACHE_TIMEOUT)
    return data


def compute_scripts_hash() -> str:
    return get_runtime_state()["scripts_hash"]


def script_row_requires_consent(script: dict[str, Any]) -> bool:
    """Whether a runtime script row is gated by user consent."""
    if "requires_consent" in script:
        return bool(script["requires_consent"])
    if script.get("always_load"):
        return False
    return not script.get("is_required", False)


def compute_scripts_hash_from_rows(
    scripts: Iterable[dict[str, Any]],
    categories: Iterable[dict[str, Any]] | None = None,
) -> str:
    """
    Canonical hash over active scripts and category purpose/policy fields:

    Script line:
      {id}|{category_id}|{category.code}|{placement}|{always_load}|
      {is_required}|{requires_consent}|{sha256(code)}

    Category line (informed consent — purpose text + required flag):
      cat|{id}|{code}|{is_required}|{sha256(title)}|{sha256(description)}

    joined by newline, then sha256.
    """
    lines: list[str] = []
    for s in sorted(scripts, key=lambda x: (x.get("order", 0), x["id"])):
        code_hash = hashlib.sha256(s["code"].encode("utf-8")).hexdigest()
        always = "1" if s.get("always_load") else "0"
        is_req = "1" if s.get("is_required") else "0"
        needs = "1" if script_row_requires_consent(s) else "0"
        lines.append(
            f"{s['id']}|{s['category_id']}|{s['category_code']}|{s['placement']}|"
            f"{always}|{is_req}|{needs}|{code_hash}"
        )
    if categories is not None:
        for c in sorted(categories, key=lambda x: (x.get("order", 0), x["id"])):
            title_h = hashlib.sha256((c.get("title") or "").encode("utf-8")).hexdigest()
            desc_h = hashlib.sha256(
                (c.get("description") or "").encode("utf-8")
            ).hexdigest()
            is_req = "1" if c.get("is_required") else "0"
            lines.append(f"cat|{c['id']}|{c['code']}|{is_req}|{title_h}|{desc_h}")
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Consent payload / cookies
# ---------------------------------------------------------------------------


@dataclass
class ConsentState:
    consent_id: uuid.UUID
    categories: list[str] = field(default_factory=list)
    banner_id: int = 0
    banner_version: int = 0
    scripts_hash: str = ""
    valid: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": 1,
            "consent_id": str(self.consent_id),
            "categories": list(self.categories),
            "banner_id": self.banner_id,
            "banner_version": self.banner_version,
            "scripts_hash": self.scripts_hash,
        }


def encode_consent_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if app_settings.SIGNED_COOKIE:
        return signing.dumps(raw, salt="script_consent.consent", compress=True)
    return raw


def decode_consent_payload(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        if app_settings.SIGNED_COOKIE:
            max_age = app_settings.MAX_AGE
            raw = signing.loads(
                value,
                salt="script_consent.consent",
                max_age=max_age if max_age is not None else None,
            )
        else:
            raw = value
        if isinstance(raw, str):
            data = json.loads(raw)
        elif isinstance(raw, dict):
            data = raw
        else:
            return None
        if not isinstance(data, dict):
            return None
        return data
    except (
        signing.BadSignature,
        signing.SignatureExpired,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return None


def _cookie_secure() -> bool:
    if app_settings.COOKIE_SECURE is not None:
        return bool(app_settings.COOKIE_SECURE)
    from django.conf import settings as dj_settings

    return bool(getattr(dj_settings, "SESSION_COOKIE_SECURE", False))


def _cookie_kwargs(max_age: int | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "path": app_settings.COOKIE_PATH,
        "samesite": app_settings.COOKIE_SAMESITE,
        "secure": _cookie_secure(),
        "httponly": app_settings.COOKIE_HTTPONLY,
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
    return kwargs


def set_consent_cookies(response: HttpResponse, state: ConsentState) -> None:
    payload = encode_consent_payload(state.to_dict())
    max_age = app_settings.MAX_AGE
    response.set_cookie(
        app_settings.CONSENT_COOKIE,
        payload,
        **_cookie_kwargs(max_age),
    )
    if app_settings.SET_CONSENT_ID_COOKIE:
        response.set_cookie(
            app_settings.CONSENT_ID_COOKIE,
            str(state.consent_id),
            **_cookie_kwargs(max_age),
        )


def clear_consent_cookies(response: HttpResponse) -> None:
    # Always clear the optional id cookie too (may exist from older installs).
    for name in (app_settings.CONSENT_COOKIE, app_settings.CONSENT_ID_COOKIE):
        response.delete_cookie(
            name,
            path=app_settings.COOKIE_PATH,
            samesite=app_settings.COOKIE_SAMESITE,
        )


def dismiss_max_age_seconds() -> int:
    """Seconds until dismiss cookie expires."""
    if app_settings.DISMISS_MAX_AGE is not None:
        return int(app_settings.DISMISS_MAX_AGE)

    now = timezone.localtime()
    end_of_day = datetime.combine(now.date(), time(23, 59, 59), tzinfo=now.tzinfo)
    delta = end_of_day - now
    # At least 1 second so cookie is still set near midnight
    return max(int(delta.total_seconds()), 1)


def set_dismiss_cookie(response: HttpResponse) -> None:
    response.set_cookie(
        app_settings.DISMISS_COOKIE,
        "1",
        **_cookie_kwargs(dismiss_max_age_seconds()),
    )


def clear_dismiss_cookie(response: HttpResponse) -> None:
    response.delete_cookie(
        app_settings.DISMISS_COOKIE,
        path=app_settings.COOKIE_PATH,
        samesite=app_settings.COOKIE_SAMESITE,
    )


def is_dismissed(request: HttpRequest) -> bool:
    return bool(request.COOKIES.get(app_settings.DISMISS_COOKIE))


def get_consent_from_request(request: HttpRequest) -> ConsentState | None:
    """Parse consent cookie without validating against current server state."""
    raw = request.COOKIES.get(app_settings.CONSENT_COOKIE)
    data = decode_consent_payload(raw) if raw else None
    if not data:
        return None
    try:
        consent_id = uuid.UUID(str(data["consent_id"]))
        categories = list(data.get("categories") or [])
        banner_version = int(data["banner_version"])
        scripts_hash = str(data["scripts_hash"])
        # banner_id is required for multi-banner correctness; missing → invalid parse
        if "banner_id" not in data or data["banner_id"] is None:
            return None
        banner_id = int(data["banner_id"])
    except (KeyError, TypeError, ValueError):
        return None
    return ConsentState(
        consent_id=consent_id,
        categories=categories,
        banner_id=banner_id,
        banner_version=banner_version,
        scripts_hash=scripts_hash,
        valid=False,
    )


def get_valid_consent(request: HttpRequest) -> ConsentState | None:
    state = get_consent_from_request(request)
    if state is None:
        return None
    runtime = get_runtime_state()
    if state.banner_id != runtime["banner"]["id"]:
        return None
    if state.banner_version != runtime["version"]:
        return None
    if state.scripts_hash != runtime["scripts_hash"]:
        return None
    state.valid = True
    return state


def has_consent_gated_scripts() -> bool:
    """True if any active insert needs explicit user consent."""
    return bool(get_runtime_state().get("has_consent_gated_scripts"))


def should_show_banner(
    request: HttpRequest,
    *,
    consent: ConsentState | None | object = _UNSET,
) -> bool:
    """
    Banner only when there are inserts that require consent and are not yet
    covered by a valid consent cookie (and banner was not dismissed today).
    Unconditional inserts (always_load / required category) do not trigger it.

    Pass ``consent`` when already resolved to avoid a second lookup.
    """
    if not has_consent_gated_scripts():
        return False
    if consent is _UNSET:
        consent = get_valid_consent(request)
    if consent is not None:
        return False
    return not is_dismissed(request)


def scripts_for_placement(
    request: HttpRequest,
    placement: str,
    *,
    consent: ConsentState | None | object = _UNSET,
) -> list[dict[str, Any]]:
    """Active scripts for placement allowed by current consent."""
    runtime = get_runtime_state()
    if consent is _UNSET:
        consent = get_valid_consent(request)
    accepted = set(consent.categories) if isinstance(consent, ConsentState) else set()

    result = []
    for s in runtime["scripts"]:
        if s["placement"] != placement:
            continue
        # Unconditional: always_load or required category
        if s.get("always_load") or s["is_required"]:
            result.append(s)
            continue
        if s["category_code"] in accepted:
            result.append(s)
    return result


def categories_for_banner() -> list[dict[str, Any]]:
    """
    Categories relevant for the consent UI:
    required ones, plus optional ones that have at least one consent-gated script.
    """
    runtime = get_runtime_state()
    gated_codes = {
        s["category_code"] for s in runtime["scripts"] if script_row_requires_consent(s)
    }
    result = []
    for c in runtime["categories"]:
        if c["is_required"] or c["code"] in gated_codes:
            result.append(c)
    return result


def anonymize_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    if not app_settings.ANONYMIZE_IP:
        return ip
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv4Address):
        # zero last octet
        parts = str(addr).split(".")
        parts[-1] = "0"
        return ".".join(parts)
    # IPv6: keep /48
    packed = bytearray(addr.packed)
    for i in range(6, 16):
        packed[i] = 0
    return str(ipaddress.IPv6Address(bytes(packed)))


def get_client_ip(request: HttpRequest) -> str | None:
    """
    Client IP for audit log.

    By default uses REMOTE_ADDR only. Set TRUST_X_FORWARDED_FOR=True only when
    a reverse proxy overwrites X-Forwarded-For (spoofing otherwise weakens audit).
    """
    if app_settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
    else:
        ip = request.META.get("REMOTE_ADDR")
    return anonymize_ip(ip)


def sanitize_privacy_policy_url(url: str | None) -> str | None:
    """Allow only relative paths or http(s) URLs; block javascript:/data: schemes."""
    if not url:
        return None
    value = str(url).strip()
    if not value:
        return None
    lower = value.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:")):
        return None
    if value.startswith("//"):
        return None
    if value.startswith("/"):
        return value
    if lower.startswith(("https://", "http://")):
        return value
    return None


def resolve_accepted_categories(action: str, category_codes: list[str] | None = None):
    """
    Resolve ScriptCategory queryset for a consent action.
    Always includes active required categories.
    """
    from script_consent.models import ScriptCategory

    active = ScriptCategory.objects.filter(is_active=True)
    required = active.filter(is_required=True)

    if action == "accept_all":
        return list(active.order_by("order", "id"))
    if action == "reject_optional":
        return list(required.order_by("order", "id"))
    if action == "custom":
        codes = set(category_codes or [])
        optional = active.filter(is_required=False, code__in=codes)
        # union required + selected optional, preserve order
        by_id = {c.id: c for c in required}
        for c in optional:
            by_id[c.id] = c
        return sorted(by_id.values(), key=lambda c: (c.order, c.id))
    if action == "withdraw":
        return []
    raise ValueError(f"Unknown action: {action}")


def build_consent_state(
    consent_id: uuid.UUID,
    categories: Iterable,
) -> ConsentState:
    runtime = get_runtime_state()
    codes = [c.code if hasattr(c, "code") else str(c) for c in categories]
    return ConsentState(
        consent_id=consent_id,
        categories=codes,
        banner_id=int(runtime["banner"]["id"]),
        banner_version=runtime["version"],
        scripts_hash=runtime["scripts_hash"],
        valid=True,
    )
