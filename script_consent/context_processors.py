from script_consent.conf import app_settings
from script_consent.utils import (
    categories_for_banner,
    get_runtime_state,
    get_valid_consent,
    sanitize_privacy_policy_url,
    scripts_for_placement,
    should_show_banner,
)


def script_consent(request):
    """
    Template context:
    - show_consent_banner
    - consent_scripts_head / body_start / body_end
    - current_consent
    - script_consent_* extras for the banner template
    """
    runtime = get_runtime_state()
    consent = get_valid_consent(request)

    return {
        "show_consent_banner": should_show_banner(request, consent=consent),
        "consent_scripts_head": scripts_for_placement(request, "head", consent=consent),
        "consent_scripts_body_start": scripts_for_placement(
            request, "body_start", consent=consent
        ),
        "consent_scripts_body_end": scripts_for_placement(
            request, "body_end", consent=consent
        ),
        "current_consent": consent,
        "script_consent_categories": categories_for_banner(),
        "script_consent_banner": runtime["banner"],
        "script_consent_privacy_url": sanitize_privacy_policy_url(
            app_settings.PRIVACY_POLICY_URL
        ),
        "script_consent_scripts_hash": runtime["scripts_hash"],
    }
