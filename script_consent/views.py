import json
import uuid

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from script_consent.models import ConsentRecord
from script_consent.utils import (
    build_consent_state,
    clear_consent_cookies,
    clear_dismiss_cookie,
    get_client_ip,
    get_consent_from_request,
    get_runtime_state,
    resolve_accepted_categories,
    set_consent_cookies,
    set_dismiss_cookie,
)


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:2000]


@require_POST
def accept_consent(request):
    """
    Accept consent: accept_all | reject_optional | custom.
    Body JSON: {"action": "...", "categories": ["analytics", ...]}
    """
    data = _json_body(request)
    action = (data.get("action") or "").strip()
    action_map = {
        "accept_all": ConsentRecord.Action.ACCEPT_ALL,
        "reject_optional": ConsentRecord.Action.REJECT_OPTIONAL,
        "custom": ConsentRecord.Action.CUSTOM,
        # aliases from UI
        "only_required": ConsentRecord.Action.REJECT_OPTIONAL,
    }
    if action not in action_map:
        return JsonResponse(
            {"ok": False, "error": "invalid_action"},
            status=400,
        )

    record_action = action_map[action]
    resolve_key = (
        "reject_optional"
        if record_action == ConsentRecord.Action.REJECT_OPTIONAL
        else (
            "accept_all"
            if record_action == ConsentRecord.Action.ACCEPT_ALL
            else "custom"
        )
    )
    categories = resolve_accepted_categories(
        resolve_key,
        data.get("categories") or [],
    )

    existing = get_consent_from_request(request)
    consent_id = existing.consent_id if existing else uuid.uuid4()

    runtime = get_runtime_state()
    user = request.user if getattr(request.user, "is_authenticated", False) else None

    with transaction.atomic():
        record = ConsentRecord.objects.create(
            consent_id=consent_id,
            user=user if user and user.is_authenticated else None,
            ip_address=get_client_ip(request),
            user_agent=_user_agent(request),
            action=record_action,
            banner_version=runtime["version"],
            scripts_hash=runtime["scripts_hash"],
        )
        record.accepted_categories.set(categories)

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
    set_consent_cookies(response, state)
    clear_dismiss_cookie(response)
    return response


@require_POST
def dismiss_banner(request):
    """Close banner for the rest of the day (not consent)."""
    response = JsonResponse({"ok": True, "action": "dismiss"})
    set_dismiss_cookie(response)
    return response


@require_POST
def withdraw_consent(request):
    """Withdraw consent: log record and clear consent + dismiss cookies."""
    existing = get_consent_from_request(request)
    consent_id = existing.consent_id if existing else uuid.uuid4()
    runtime = get_runtime_state()
    user = request.user if getattr(request.user, "is_authenticated", False) else None

    ConsentRecord.objects.create(
        consent_id=consent_id,
        user=user if user and user.is_authenticated else None,
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        action=ConsentRecord.Action.WITHDRAW,
        banner_version=runtime["version"],
        scripts_hash=runtime["scripts_hash"],
    )

    response = JsonResponse(
        {
            "ok": True,
            "action": "withdraw",
            "consent_id": str(consent_id),
            "reload": True,
        }
    )
    clear_consent_cookies(response)
    clear_dismiss_cookie(response)
    return response
