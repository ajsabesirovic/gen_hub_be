from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

class CustomAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        if "password_reset_url" in context:
            uid = context["uid"]
            token = context["token"]
            context["password_reset_url"] = (
                f"{settings.FRONTEND_RESET_PASSWORD_URL}{uid}/{token}/"
            )
        super().send_mail(template_prefix, email, context)
