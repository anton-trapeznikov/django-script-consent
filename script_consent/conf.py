from django.conf import settings

DEFAULTS = {
    "CONSENT_COOKIE": "script_consent",
    "DISMISS_COOKIE": "script_banner_dismissed",
    # Optional second cookie with plain consent UUID (off by default; value is
    # already inside the signed consent payload).
    "CONSENT_ID_COOKIE": "script_consent_id",
    "SET_CONSENT_ID_COOKIE": False,
    "MAX_AGE": 60 * 60 * 24 * 365,  # 1 year
    "DISMISS_MAX_AGE": None,  # None = until end of local calendar day
    "ANONYMIZE_IP": True,
    # Only use X-Forwarded-For when a trusted reverse proxy overwrites it.
    "TRUST_X_FORWARDED_FOR": False,
    "CACHE_TIMEOUT": 60 * 60,
    "CACHE_KEY": "script_consent:runtime",
    "COOKIE_SAMESITE": "Lax",
    "COOKIE_SECURE": None,  # None → SESSION_COOKIE_SECURE
    "COOKIE_HTTPONLY": True,
    "SIGNED_COOKIE": True,
    "COOKIE_PATH": "/",
    # Floating button to reopen banner / change or withdraw consent
    "SHOW_SETTINGS_BUTTON": True,  # "Consent settings" launcher
    # None = keep ConsentRecord rows forever; integer days for purge command
    "CONSENT_RECORD_RETENTION_DAYS": None,
}


class ScriptConsentSettings:
    def __getattr__(self, name: str):
        if name not in DEFAULTS:
            raise AttributeError(f"Unknown SCRIPT_CONSENT setting: {name}")
        user_settings = getattr(settings, "SCRIPT_CONSENT", None) or {}
        if name in user_settings:
            return user_settings[name]
        return DEFAULTS[name]

    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in DEFAULTS}


app_settings = ScriptConsentSettings()
