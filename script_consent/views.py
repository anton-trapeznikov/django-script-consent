import json
import uuid
from typing import Any

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from script_consent import cookies, repositories
from script_consent.cache import get_runtime_state
from script_consent.consent import build_consent_state
from script_consent.ip import get_client_ip
from script_consent.models import ConsentRecord
from script_consent.services import resolve_accepted_categories

_ACCEPT_ACTIONS: dict[str, tuple[str, str]] = {
    "accept_all": ("accept_all", ConsentRecord.Action.ACCEPT_ALL),
    "reject_optional": ("reject_optional", ConsentRecord.Action.REJECT_OPTIONAL),
    "custom": ("custom", ConsentRecord.Action.CUSTOM),
    "only_required": ("reject_optional", ConsentRecord.Action.REJECT_OPTIONAL),
}


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _user_agent(request: HttpRequest) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:2000]


def _authenticated_user(request: HttpRequest):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def _consent_id_from_request(request: HttpRequest) -> uuid.UUID:
    existing = cookies.get_consent_from_request(request)
    return existing.consent_id if existing else uuid.uuid4()


def _error(error: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": error}, status=status)


def _log_consent(
    request: HttpRequest,
    *,
    consent_id: uuid.UUID,
    action: str,
    runtime: dict[str, Any],
    categories,
) -> None:
    repositories.create_consent_record(
        consent_id=consent_id,
        user=_authenticated_user(request),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        action=action,
        banner_version=runtime["version"],
        scripts_hash=runtime["scripts_hash"],
        categories=categories,
    )


@require_POST
def accept_consent(request):
    data = _json_body(request)
    action = (data.get("action") or "").strip()
    if action not in _ACCEPT_ACTIONS:
        return _error("invalid_action")

    resolve_key, record_action = _ACCEPT_ACTIONS[action]

    runtime = get_runtime_state()
    if runtime.get("banner") is None:
        return _error("no_active_banner")

    categories = resolve_accepted_categories(
        resolve_key,
        data.get("categories") or [],
    )
    consent_id = _consent_id_from_request(request)

    with transaction.atomic():
        _log_consent(
            request,
            consent_id=consent_id,
            action=record_action,
            runtime=runtime,
            categories=categories,
        )

    state = build_consent_state(consent_id, categories)
    response = JsonResponse(
        {
            "ok": True,
            "action": record_action,
            "consent_id": str(consent_id),
            "categories": state.categories,
            "banner_version": state.banner_version,
            "scripts_hash": state.scripts_hash,
            "reload": True,
        }
    )
    cookies.set_consent_cookies(response, state)
    cookies.clear_dismiss_cookie(response)
    return response


@require_POST
def dismiss_banner(request):
    response = JsonResponse({"ok": True, "action": "dismiss"})
    cookies.set_dismiss_cookie(response)
    return response


@require_POST
def withdraw_consent(request):
    consent_id = _consent_id_from_request(request)
    runtime = get_runtime_state()
    _log_consent(
        request,
        consent_id=consent_id,
        action=ConsentRecord.Action.WITHDRAW,
        runtime=runtime,
        categories=[],
    )

    response = JsonResponse(
        {
            "ok": True,
            "action": "withdraw",
            "consent_id": str(consent_id),
            "reload": True,
        }
    )
    cookies.clear_consent_cookies(response)
    cookies.clear_dismiss_cookie(response)
    return response
