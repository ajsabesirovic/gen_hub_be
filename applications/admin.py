from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("task", "volunteer", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("task__title", "volunteer__username")
