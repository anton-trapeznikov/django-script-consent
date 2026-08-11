from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from script_consent.cache import invalidate_runtime_cache
from script_consent.models import BannerConfig, ScriptCategory, ScriptSnippet


@receiver(post_save, sender=BannerConfig)
@receiver(post_delete, sender=BannerConfig)
@receiver(post_save, sender=ScriptSnippet)
@receiver(post_delete, sender=ScriptSnippet)
@receiver(post_save, sender=ScriptCategory)
@receiver(post_delete, sender=ScriptCategory)
def clear_script_consent_cache(**kwargs):
    invalidate_runtime_cache()
