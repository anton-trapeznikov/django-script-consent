"""Ensure demo console.log snippets exist (for DBs that already ran 0001)."""

from django.db import migrations


def seed_demo_snippets(apps, schema_editor):
    ScriptCategory = apps.get_model("script_consent", "ScriptCategory")
    ScriptSnippet = apps.get_model("script_consent", "ScriptSnippet")

    snippets = [
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
    for data in snippets:
        cat = ScriptCategory.objects.filter(code=data["category_code"]).first()
        if cat is None:
            continue
        ScriptSnippet.objects.update_or_create(
            name=data["name"],
            defaults={
                "category": cat,
                "placement": data["placement"],
                "code": data["code"],
                "always_load": data["always_load"],
                "order": data["order"],
                "is_active": data["is_active"],
            },
        )


def unseed_demo_snippets(apps, schema_editor):
    ScriptSnippet = apps.get_model("script_consent", "ScriptSnippet")
    ScriptSnippet.objects.filter(
        name__in=["Demo · Essential", "Demo · Analytics", "Demo · Marketing"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("script_consent", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_demo_snippets, unseed_demo_snippets),
    ]
