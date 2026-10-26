from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user=request.user)

    def has_add_permission(self, request):
        return False
