import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.account.internal.flows.email_verification_by_code import (
    EmailVerificationProcess,
)
from allauth.core.internal.cryptokit import compare_user_code

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse

from users.models import EmailVerificationAttempt
from users.views import _persist_confirmation_metadata
from users.throttles import VerifyEmailCodeThrottle


logger = logging.getLogger(__name__)


class VerifyEmailCodeSerializer(serializers.Serializer):
    
    code = serializers.CharField(
        required=True,
        write_only=True,
        help_text="6-digit verification code sent to the user's email address.",
    )


class VerifyEmailCodeView(APIView):
    """
    Verify a user's email address using a short-lived verification code.
    """

    permission_classes = [AllowAny]
    serializer_class = VerifyEmailCodeSerializer
    throttle_classes = [VerifyEmailCodeThrottle]

    def _process_expired(self, process: EmailVerificationProcess) -> bool:
      
        timeout_seconds = getattr(
            settings,
            "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT",
            getattr(allauth_account_settings, "EMAIL_VERIFICATION_BY_CODE_TIMEOUT", 2 * 60),
        )
        expires_at = getattr(process, "expires_at", None)
        if expires_at:
            return timezone.now() >= expires_at

        started_at = getattr(process, "created_at", None) or getattr(
            process, "started_at", None
        )
        if started_at:
            return timezone.now() >= started_at + timedelta(seconds=timeout_seconds)

        return not process.is_valid()

    def _process_email(self, process: EmailVerificationProcess) -> str | None:
        return getattr(process, "email", None)

    def _get_latest_confirmation(self, email_address: EmailAddress) -> EmailConfirmation:
        confirmation = (
            EmailConfirmation.objects.filter(email_address=email_address)
            .order_by("-created")
            .first()
        )
        if not confirmation:
            confirmation = EmailConfirmation.create(email_address=email_address)
            confirmation.sent = timezone.now()
            confirmation.save()
        elif not confirmation.sent:
            confirmation.sent = confirmation.created
            confirmation.save()
        return confirmation

    def _get_or_create_attempt(
        self, email_address: EmailAddress
    ) -> EmailVerificationAttempt:
    
        confirmation = self._get_latest_confirmation(email_address)
        attempt, _ = EmailVerificationAttempt.objects.get_or_create(
            email_confirmation=confirmation
        )
        return attempt

    @extend_schema(
        request=VerifyEmailCodeSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="VerifyEmailCodeSuccess",
                    fields={
                        "detail": serializers.CharField(),
                        "email": serializers.EmailField(),
                    },
                ),
                description="Email successfully verified.",
            ),
            400: OpenApiResponse(
                response=inline_serializer(
                    name="VerifyEmailCodeError",
                    fields={"detail": serializers.CharField()},
                ),
                description="Invalid input or too many invalid attempts.",
            ),
        },
        tags=["Auth"],
    )
    def post(self, request, *args, **kwargs):
        if not allauth_account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
            return Response(
                {"detail": _("Code verification is not enabled.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        process = EmailVerificationProcess.resume(request)
        if not process:
            return Response(
                {
                    "detail": _(
                        "No active verification process found. "
                        "Please ensure you are using the same browser/session "
                        "where you registered, or request a new verification code."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._process_expired(process):
            process.abort()
            return Response(
                {"detail": _("Verification code has expired. Please request a new one.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_value = self._process_email(process)
        if not email_value:
            logger.warning("Email verification process missing email attribute")
            return Response(
                {"detail": _("Verification process is invalid.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            email_address = EmailAddress.objects.get(email=email_value.lower())
        except EmailAddress.DoesNotExist:
            return Response(
                {"detail": _("No email address found for this verification process.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            request.user.is_authenticated
            and email_address.user is not None
            and email_address.user != request.user
        ):
            return Response(
                {"detail": _("Invalid verification code.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attempt = self._get_or_create_attempt(email_address)

        if attempt.attempts >= 3:
            return Response(
                {
                    "detail": _(
                        "Too many invalid attempts. Request a new verification email."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not compare_user_code(actual=code, expected=process.code):
            attempt.attempts += 1
            attempt.save(update_fields=["attempts"])
            logger.info(
                "Invalid email verification code attempt",
                extra={
                    "email": email_address.email,
                    "attempts": attempt.attempts,
                },
            )
            return Response(
                {"detail": _("Invalid verification code.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            verified_email_address = process.finish()
            
            if verified_email_address and verified_email_address.verified:
                _persist_confirmation_metadata(verified_email_address)
                
                logger.info(
                    "Email successfully verified via code",
                    extra={"email": verified_email_address.email},
                )
                
                return Response(
                    {
                        "detail": _("Email successfully verified."),
                        "email": verified_email_address.email,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": _("Email verification failed.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as exc:
            logger.error(
                "Email verification failed with ValueError: %s",
                exc,
                extra={"email": email_address.email},
            )
            return Response(
                {
                    "detail": _(
                        "Cannot verify email: User account issue. Please contact support."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error during email verification: %s", exc)
            return Response(
                {
                    "detail": _(
                        "An error occurred during email verification. Please try again."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


