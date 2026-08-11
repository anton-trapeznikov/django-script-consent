import hashlib
from collections.abc import Iterable
from typing import Any


def script_row_requires_consent(script: dict[str, Any]) -> bool:
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
