from django.apps import AppConfig


class AvailabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'availability'

    def ready(self):
        from . import signals  # noqa: F401
