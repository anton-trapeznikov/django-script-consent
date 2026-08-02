import uuid

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class RuntimeCacheStamp(models.Model):
    """
    Singleton generation counter for the runtime cache key.

    Stored in the DB so LocMem/multi-process workers all miss after invalidation
    instead of serving stale snippet HTML until TTL expiry.
    """

    key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    generation = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Runtime cache stamp")
        verbose_name_plural = _("Runtime cache stamps")

    def __str__(self) -> str:
        return f"generation={self.generation}"

    @classmethod
    def current(cls) -> int:
        try:
            return int(cls.objects.values_list("generation", flat=True).get(pk=1))
        except cls.DoesNotExist:
            cls.objects.create(pk=1, generation=0)
            return 0

    @classmethod
    def bump(cls) -> int:
        cls.objects.get_or_create(pk=1, defaults={"generation": 0})
        cls.objects.filter(pk=1).update(generation=F("generation") + 1)
        return int(cls.objects.values_list("generation", flat=True).get(pk=1))


class ScriptCategory(models.Model):
    """Consent category catalog (groups of scripts / snippets)."""

    code = models.SlugField(_("Code"), max_length=64, unique=True)
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    is_required = models.BooleanField(
        _("Required"),
        default=False,
        help_text=_("Essential scripts: cannot be refused"),
    )
    order = models.PositiveIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Script category")
        verbose_name_plural = _("Script categories")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.title


class BannerConfig(models.Model):
    """Banner text configuration with automatic versioning."""

    title = models.CharField(_("Title"), max_length=255)
    text = models.TextField(_("Text"), help_text=_("Simple HTML is allowed"))
    version = models.PositiveIntegerField(_("Version"), default=1)
    is_active = models.BooleanField(_("Active"), default=True)
    updated_at = models.DateTimeField(_("Updated"), auto_now=True)

    class Meta:
        verbose_name = _("Banner configuration")
        verbose_name_plural = _("Banner configurations")
        ordering = ["-is_active", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk:
            try:
                previous = BannerConfig.objects.get(pk=self.pk)
            except BannerConfig.DoesNotExist:
                previous = None
            if previous is not None:
                text_changed = (
                    previous.title != self.title or previous.text != self.text
                )
                # Bump when copy changes or when this row becomes the active
                # banner (switching active config must invalidate prior consent).
                activated = self.is_active and not previous.is_active
                if text_changed or activated:
                    self.version = previous.version + 1
                    if update_fields is not None:
                        kwargs["update_fields"] = set(update_fields) | {"version"}

        super().save(*args, **kwargs)

        if self.is_active:
            BannerConfig.objects.exclude(pk=self.pk).filter(is_active=True).update(
                is_active=False
            )

    @classmethod
    def get_solo(cls) -> "BannerConfig":
        """Return the active banner config, creating a default if needed."""
        from script_consent.defaults import DEFAULT_BANNER

        obj = cls.objects.filter(is_active=True).order_by("-updated_at").first()
        if obj is not None:
            return obj
        obj = cls.objects.order_by("-updated_at").first()
        if obj is not None:
            if not obj.is_active:
                obj.is_active = True
                obj.save(update_fields=["is_active", "updated_at"])
            return obj
        return cls.objects.create(**DEFAULT_BANNER)


class ScriptSnippet(models.Model):
    """HTML/JS snippet managed via consent."""

    class Placement(models.TextChoices):
        HEAD = "head", _("Head")
        BODY_START = "body_start", _("Body start")
        BODY_END = "body_end", _("Body end")

    name = models.CharField(_("Name"), max_length=255)
    category = models.ForeignKey(
        ScriptCategory,
        on_delete=models.PROTECT,
        related_name="scripts",
        verbose_name=_("Category"),
    )
    placement = models.CharField(
        _("Placement"),
        max_length=16,
        choices=Placement.choices,
        default=Placement.BODY_END,
    )
    code = models.TextField(_("Snippet code"), help_text=_("HTML/JS code"))
    always_load = models.BooleanField(
        _("Load without consent"),
        default=False,
        help_text=_(
            "If checked, the snippet is always loaded and does not participate "
            "in the consent prompt (regardless of category)."
        ),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Script / snippet")
        verbose_name_plural = _("Scripts / snippets")
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["is_active", "placement", "order"]),
        ]

    def __str__(self) -> str:
        return self.name

    @cached_property
    def requires_consent(self) -> bool:
        """True only if the insert is gated by user consent."""
        if self.always_load:
            return False
        return not self.category.is_required


class ConsentRecord(models.Model):
    """Record of obtaining, changing, or withdrawing consent."""

    class Action(models.TextChoices):
        ACCEPT_ALL = "accept_all", _("Accept all")
        REJECT_OPTIONAL = "reject_optional", _("Necessary only")
        CUSTOM = "custom", _("Custom selection")
        WITHDRAW = "withdraw", _("Withdraw")

    consent_id = models.UUIDField(_("Consent ID"), default=uuid.uuid4, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="script_consents",
        verbose_name=_("User"),
    )
    created_at = models.DateTimeField(_("Created"), auto_now_add=True)
    ip_address = models.GenericIPAddressField(_("IP"), null=True, blank=True)
    user_agent = models.TextField(_("User-Agent"), blank=True)
    action = models.CharField(_("Action"), max_length=32, choices=Action.choices)
    accepted_categories = models.ManyToManyField(
        ScriptCategory,
        blank=True,
        related_name="consent_records",
        verbose_name=_("Accepted categories"),
    )
    banner_version = models.PositiveIntegerField(_("Banner version"))
    scripts_hash = models.CharField(_("Scripts hash"), max_length=64)

    class Meta:
        verbose_name = _("Consent record")
        verbose_name_plural = _("Consent records")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.consent_id} / {self.action} @ {self.created_at}"
