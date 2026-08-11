from script_consent import repositories
from script_consent.models import ScriptCategory


def sanitize_privacy_policy_url(url: str | None) -> str | None:
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


def resolve_accepted_categories(
    action: str,
    category_codes: list[str] | None = None,
) -> list[ScriptCategory]:
    match action:
        case "withdraw":
            return []

        case "accept_all":
            return repositories.list_active_categories()

        case "reject_optional":
            return repositories.list_required_categories()

        case "custom":
            required = repositories.list_required_categories()
            optional = repositories.list_optional_categories_by_codes(
                category_codes or []
            )
            by_id = {c.id: c for c in required}

            for c in optional:
                by_id[c.id] = c

            return sorted(by_id.values(), key=lambda c: (c.order, c.id))

        case _:
            raise ValueError(f"Unknown action: {action}")
