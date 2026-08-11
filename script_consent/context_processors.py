from script_consent import consent
from script_consent.cache import get_runtime_state


def script_consent(request):
    """
    Template context:
    - show_consent_banner / banner shell fields
    - consent_scripts_head / body_start / body_end
    - current_consent
    - script_consent_scripts_hash
    """
    state = consent.get_valid_consent(request)
    ctx = consent.banner_template_context(request, consent=state)
    runtime = get_runtime_state()
    ctx.update(
        {
            "current_consent": state,
            "consent_scripts_head": consent.scripts_for_placement(
                request, "head", consent=state
            ),
            "consent_scripts_body_start": consent.scripts_for_placement(
                request, "body_start", consent=state
            ),
            "consent_scripts_body_end": consent.scripts_for_placement(
                request, "body_end", consent=state
            ),
            "script_consent_scripts_hash": runtime["scripts_hash"],
        }
    )
    return ctx
