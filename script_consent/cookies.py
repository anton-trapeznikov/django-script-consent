import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from django.conf import settings as dj_settings
from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from script_consent.conf import app_settings


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
    for name in (app_settings.CONSENT_COOKIE, app_settings.CONSENT_ID_COOKIE):
        response.delete_cookie(
            name,
            path=app_settings.COOKIE_PATH,
            samesite=app_settings.COOKIE_SAMESITE,
        )


def dismiss_max_age_seconds() -> int:
    if app_settings.DISMISS_MAX_AGE is not None:
        return int(app_settings.DISMISS_MAX_AGE)

    now = timezone.localtime()
    end_of_day = datetime.combine(now.date(), time(23, 59, 59), tzinfo=now.tzinfo)
    delta = end_of_day - now

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
