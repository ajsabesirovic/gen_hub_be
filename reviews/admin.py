from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("task", "senior", "volunteer", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("task__title", "senior__username", "volunteer__username")
