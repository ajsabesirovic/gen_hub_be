from django.db.models.signals import post_save
from django.dispatch import receiver

from allauth.account.models import EmailConfirmation

from .models import EmailVerificationAttempt


@receiver(post_save, sender=EmailConfirmation)
def create_email_verification_attempt(
    sender, instance: EmailConfirmation, created: bool, **kwargs
) -> None:
    """
    Ensure there is an `EmailVerificationAttempt` for every `EmailConfirmation`.

    The attempt object is created once, at the moment allauth generates a new
    `EmailConfirmation` record. Historic confirmations are left untouched and
    their attempt rows (if any) are never re-used for newer keys.
    """
    if not created:
        return

    EmailVerificationAttempt.objects.get_or_create(email_confirmation=instance)


