from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="registration.ensure_profile_exists",
)
def ensure_profile_exists(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    Profile.objects.get_or_create(user=instance)
    if not created:
        instance.profile.save()
