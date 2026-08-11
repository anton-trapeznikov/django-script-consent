import uuid
from collections.abc import Iterable
from typing import Any

from django.http import HttpRequest

from script_consent import cookies
from script_consent.cache import get_runtime_state
from script_consent.conf import app_settings
from script_consent.hashing import script_row_requires_consent
from script_consent.services import sanitize_privacy_policy_url

_UNSET: Any = object()


def get_valid_consent(request: HttpRequest) -> cookies.ConsentState | None:
    state = cookies.get_consent_from_request(request)

    if state is None:
        return None

    runtime = get_runtime_state()
    banner = runtime.get("banner")

    if banner is None:
        return None

    if state.banner_id != banner["id"]:
        return None

    if state.banner_version != runtime["version"]:
        return None

    if state.scripts_hash != runtime["scripts_hash"]:
        return None

    state.valid = True

    return state


def has_consent_gated_scripts() -> bool:
    return bool(get_runtime_state().get("has_consent_gated_scripts"))


def should_show_banner(
    request: HttpRequest,
    *,
    consent: cookies.ConsentState | None | object = _UNSET,
) -> bool:
    runtime = get_runtime_state()

    if runtime.get("banner") is None:
        return False

    if not runtime.get("has_consent_gated_scripts"):
        return False

    if consent is _UNSET:
        consent = get_valid_consent(request)

    if consent is not None:
        return False

    return not cookies.is_dismissed(request)


def scripts_for_placement(
    request: HttpRequest,
    placement: str,
    *,
    consent: cookies.ConsentState | None | object = _UNSET,
) -> list[dict[str, Any]]:
    runtime = get_runtime_state()
    if consent is _UNSET:
        consent = get_valid_consent(request)

    accepted = (
        set(consent.categories) if isinstance(consent, cookies.ConsentState) else set()
    )

    result = []
    for s in runtime["scripts"]:
        if s["placement"] != placement:
            continue

        if s.get("always_load") or s["is_required"]:
            result.append(s)
            continue

        if s["category_code"] in accepted:
            result.append(s)

    return result


def categories_for_banner() -> list[dict[str, Any]]:
    runtime = get_runtime_state()
    gated_codes = {
        s["category_code"] for s in runtime["scripts"] if script_row_requires_consent(s)
    }
    result = []

    for c in runtime["categories"]:
        if c["is_required"] or c["code"] in gated_codes:
            result.append(c)

    return result


def build_consent_state(
    consent_id: uuid.UUID,
    categories: Iterable,
) -> cookies.ConsentState:
    runtime = get_runtime_state()
    banner = runtime.get("banner")

    if banner is None:
        raise ValueError("Cannot build consent state without an active banner")

    codes = [c.code if hasattr(c, "code") else str(c) for c in categories]

    return cookies.ConsentState(
        consent_id=consent_id,
        categories=codes,
        banner_id=int(banner["id"]),
        banner_version=runtime["version"],
        scripts_hash=runtime["scripts_hash"],
        valid=True,
    )


def banner_template_context(
    request: HttpRequest | None,
    *,
    consent: cookies.ConsentState | None | object = _UNSET,
    categories: list[dict[str, Any]] | None = None,
    banner: Any = _UNSET,
    privacy_url: str | None | object = _UNSET,
) -> dict[str, Any]:
    if consent is _UNSET:
        consent = get_valid_consent(request) if request is not None else None

    if categories is None:
        categories = categories_for_banner()

    if banner is _UNSET:
        banner = get_runtime_state()["banner"]

    if privacy_url is _UNSET:
        privacy_url = app_settings.PRIVACY_POLICY_URL

    privacy_url = sanitize_privacy_policy_url(
        privacy_url if isinstance(privacy_url, str) or privacy_url is None else None
    )

    show = (
        should_show_banner(request, consent=consent) if request is not None else False
    )
    accepted = (
        list(consent.categories) if isinstance(consent, cookies.ConsentState) else []
    )

    return {
        "show_consent_banner": show,
        "show_settings_button": bool(app_settings.SHOW_SETTINGS_BUTTON),
        "script_consent_categories": categories,
        "script_consent_banner": banner,
        "script_consent_privacy_url": privacy_url,
        "accepted_category_codes": accepted,
        "request": request,
    }
