from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "volunteer", "status", "start", "end", "category")
    list_filter = ("status", "category")
    search_fields = ("title", "description", "user__username", "volunteer__username")
    ordering = ("-start",)
