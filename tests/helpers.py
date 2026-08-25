import uuid
from typing import Any
from unittest.mock import MagicMock

from django.http import HttpRequest
from django.test import RequestFactory

from script_consent.cookies import ConsentState, encode_consent_payload


def make_request(
    path: str = "/",
    *,
    cookies: dict[str, str] | None = None,
    **meta,
) -> HttpRequest:
    request = RequestFactory().get(path, **meta)
    request.COOKIES = cookies or {}

    return request


def make_runtime(
    *,
    banner: dict[str, Any] | None = None,
    version: int | None = None,
    scripts: list[dict[str, Any]] | None = None,
    categories: list[dict[str, Any]] | None = None,
    scripts_hash: str = "hash" * 16,
    has_consent_gated_scripts: bool = True,
) -> dict[str, Any]:
    if banner is None and version is None:
        banner = {
            "id": 1,
            "title": "Cookies",
            "text": "Text",
            "operator": "",
            "privacy_url": "",
            "version": 1,
            "is_active": True,
        }
        version = 1

    elif banner is not None and version is None:
        version = int(banner.get("version", 0))

    elif banner is None:
        version = version if version is not None else 0

    if categories is None:
        categories = [
            {
                "id": 1,
                "code": "technical",
                "title": "Essential",
                "description": "",
                "is_required": True,
                "order": 0,
                "is_active": True,
            },
            {
                "id": 2,
                "code": "analytics",
                "title": "Analytics",
                "description": "",
                "is_required": False,
                "order": 10,
                "is_active": True,
            },
        ]

    if scripts is None:
        scripts = [
            {
                "id": 1,
                "name": "Required",
                "category_id": 1,
                "category_code": "technical",
                "is_required": True,
                "always_load": False,
                "requires_consent": False,
                "placement": "head",
                "code": "<!-- req -->",
                "order": 0,
                "recipient": "",
            },
            {
                "id": 2,
                "name": "Optional",
                "category_id": 2,
                "category_code": "analytics",
                "is_required": False,
                "always_load": False,
                "requires_consent": True,
                "placement": "body_end",
                "code": "<!-- opt -->",
                "order": 10,
                "recipient": "",
            },
        ]

    return {
        "banner": banner,
        "version": version,
        "scripts_hash": scripts_hash,
        "scripts": scripts,
        "categories": categories,
        "has_consent_gated_scripts": has_consent_gated_scripts,
    }


def make_consent_cookie(
    *,
    consent_id: uuid.UUID | None = None,
    categories: list[str] | None = None,
    banner_id: int = 1,
    banner_version: int = 1,
    scripts_hash: str = "hash" * 16,
) -> str:
    state = ConsentState(
        consent_id=consent_id or uuid.uuid4(),
        categories=categories or ["technical", "analytics"],
        banner_id=banner_id,
        banner_version=banner_version,
        scripts_hash=scripts_hash,
        valid=False,
    )
    return encode_consent_payload(state.to_dict())


def mock_category(
    *,
    id: int = 1,
    code: str = "technical",
    is_required: bool = True,
    order: int = 0,
    is_active: bool = True,
    title: str = "Title",
    description: str = "",
) -> MagicMock:
    cat = MagicMock()

    cat.id = id
    cat.code = code
    cat.is_required = is_required
    cat.order = order
    cat.is_active = is_active
    cat.title = title
    cat.description = description

    return cat
