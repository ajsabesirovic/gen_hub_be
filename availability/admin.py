from django.contrib import admin

from .models import UserAvailability


@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "day_of_week", "date", "start_time", "end_time")
    list_filter = ("type",)
    search_fields = ("user__username",)
