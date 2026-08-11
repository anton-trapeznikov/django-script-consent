from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet
from script_consent.utils import invalidate_runtime_cache


@receiver(post_save, sender=BannerConfig)
@receiver(post_delete, sender=BannerConfig)
@receiver(post_save, sender=ScriptSnippet)
@receiver(post_delete, sender=ScriptSnippet)
@receiver(post_save, sender=ScriptCategory)
@receiver(post_delete, sender=ScriptCategory)
def clear_script_consent_cache(**kwargs):
    invalidate_runtime_cache()
