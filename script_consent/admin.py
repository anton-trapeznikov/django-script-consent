from collections.abc import Sequence
from typing import ClassVar

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from script_consent.models import (
    BannerConfig,
    ConsentRecord,
    ScriptCategory,
    ScriptSnippet,
)


@admin.register(ScriptCategory)
class ScriptCategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "is_required", "order", "is_active")
    list_editable = ("order", "is_active", "is_required")
    list_filter = ("is_required", "is_active")
    search_fields = ("code", "title")
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"code": ["title"]}
    ordering = ("order", "id")


@admin.register(ScriptSnippet)
class ScriptSnippetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "placement",
        "always_load",
        "order",
        "is_active",
    )
    list_filter = ("category", "placement", "always_load", "is_active")
    list_editable = ("order", "is_active", "always_load")
    search_fields = ("name", "code")
    ordering = ("order", "id")
    readonly_fields = ("code_preview",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "category",
                    "placement",
                    "always_load",
                    "order",
                    "is_active",
                    "code",
                    "code_preview",
                )
            },
        ),
    )

    @admin.display(description=_("Code preview"))
    def code_preview(self, obj: ScriptSnippet):
        if not obj or not obj.pk:
            return "—"
        snippet = (obj.code or "")[:500]
        return format_html(
            '<pre style="max-height:200px;overflow:auto;white-space:pre-wrap;">'
            "{}"
            "</pre>",
            snippet,
        )


@admin.register(BannerConfig)
class BannerConfigAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "is_active", "updated_at")
    list_filter = ("is_active",)
    readonly_fields = ("version", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": ("title", "text", "is_active"),
                "description": _(
                    "Changing the title or text, or activating this configuration, "
                    "automatically increments the version. Consent is bound to the "
                    "active banner id and version; switching or editing invalidates "
                    "previously granted consents."
                ),
            },
        ),
        (
            _("System"),
            {"fields": ("version", "updated_at")},
        ),
    )


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "consent_id",
        "action",
        "user",
        "banner_version",
        "scripts_hash_short",
        "created_at",
        "ip_address",
    )
    list_filter = ("action", "created_at")
    search_fields = ("consent_id", "user__username", "ip_address", "scripts_hash")
    date_hierarchy = "created_at"
    readonly_fields = (
        "consent_id",
        "user",
        "created_at",
        "ip_address",
        "user_agent",
        "action",
        "accepted_categories",
        "banner_version",
        "scripts_hash",
    )
    filter_horizontal = ("accepted_categories",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Scripts hash"))
    def scripts_hash_short(self, obj: ConsentRecord):
        h = obj.scripts_hash or ""
        return f"{h[:12]}…" if len(h) > 12 else h
