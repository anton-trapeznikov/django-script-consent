DEFAULT_CATEGORIES = [
    {
        "code": "technical",
        "title": "Essential",
        "description": (
            "Required for the website to work correctly: session, security, "
            "and consent preferences. They do not collect personal data and are not "
            "used to track users. These cannot be disabled."
        ),
        "is_required": True,
        "order": 0,
        "is_active": True,
    },
    {
        "code": "analytics",
        "title": "Analytics",
        "description": (
            "Help us understand how visitors use the site "
            "(for example, traffic counters). Used only with your consent."
        ),
        "is_required": False,
        "order": 10,
        "is_active": True,
    },
    {
        "code": "marketing",
        "title": "Marketing",
        "description": (
            "Used to show relevant ads and measure their effectiveness. "
            "Loaded only with your consent."
        ),
        "is_required": False,
        "order": 20,
        "is_active": True,
    },
]

DEFAULT_BANNER = {
    "title": "We use cookies",
    "text": (
        "This site uses cookies and similar technologies to run the service, "
        "for analytics, and (with your consent) for marketing. "
        "You may accept all categories, choose specific ones, or keep only "
        "essential cookies. See our privacy policy for details. "
        "Consent is specific to the set of active scripts at the time you agree; "
        "if that set changes, we will ask again."
    ),
    "version": 1,
    "is_active": True,
}

DEFAULT_SNIPPETS = [
    {
        "name": "Demo · Essential",
        "category_code": "technical",
        "placement": "head",
        "code": (
            "<script>"
            'console.log("[script-consent] essential / technical loaded");'
            "</script>"
        ),
        "always_load": False,
        "order": 0,
        "is_active": True,
    },
    {
        "name": "Demo · Analytics",
        "category_code": "analytics",
        "placement": "body_end",
        "code": (
            "<script>"
            'console.log("[script-consent] analytics loaded (consent required)");'
            "</script>"
        ),
        "always_load": False,
        "order": 10,
        "is_active": True,
    },
    {
        "name": "Demo · Marketing",
        "category_code": "marketing",
        "placement": "body_end",
        "code": (
            "<script>"
            'console.log("[script-consent] marketing loaded (consent required)");'
            "</script>"
        ),
        "always_load": False,
        "order": 20,
        "is_active": True,
    },
]
