from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="profiles/", blank=True, null=True)
    bio = models.TextField(blank=True)

    class Meta:
        ordering = ["user"]

    def __str__(self):
        return self.user.get_username()