import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import generics, permissions, status, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC, EmailAddress
from allauth.account import app_settings as allauth_account_settings
from allauth.account.internal.flows.email_verification import verify_email_and_resume
from allauth.account.internal.flows.email_verification_by_code import EmailVerificationProcess
from allauth.core.internal.cryptokit import compare_user_code
from dj_rest_auth.registration.serializers import ResendEmailVerificationSerializer
from dj_rest_auth.views import LoginView as BaseLoginView, UserDetailsView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import CustomLoginSerializer, UserSerializer
from .throttles import ResendEmailCodeThrottle, VerifyEmailCodeThrottle

logger = logging.getLogger(__name__)

User = get_user_model()


def _persist_confirmation_metadata(email_address, sent_at=None):
    """
    Ensure there is an EmailConfirmation record for the address and capture the
    latest time it was (re)sent.
    """
    if not email_address:
        return

    sent_at = sent_at or timezone.now()
    try:
        confirmation = (
            EmailConfirmation.objects.filter(email_address=email_address)
            .order_by("-created")
            .first()
        )
        if not confirmation:
            confirmation = EmailConfirmation.create(email_address=email_address)
        if not confirmation.sent or confirmation.sent < sent_at:
            confirmation.sent = sent_at
            confirmation.save()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist email confirmation metadata: %s", exc)


@extend_schema(tags=["auth"])
class EmailConfirmAPIView(generics.GenericAPIView):
    """
    Legacy view for link-based email confirmation (not used when code verification is enabled).
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={200: serializers.Serializer()},
        tags=["auth"],
    )
    def get(self, request, *args, **kwargs):
        key = kwargs.get('key')
        if not key:
            return Response(
                {'detail': 'Verification key is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if allauth_account_settings.EMAIL_CONFIRMATION_HMAC:
                confirmation = EmailConfirmationHMAC.from_key(key)
            else:
                confirmation = EmailConfirmation.from_key(key)

            if not confirmation:
                raise Http404()
            email_address, response = verify_email_and_resume(request, confirmation)
            
            if response:
                return Response(
                    {'detail': 'Email verification process requires additional steps.'},
                    status=status.HTTP_302_FOUND
                )
            
            if email_address and email_address.verified:
                return Response(
                    {
                        'detail': 'Email successfully verified.',
                        'email': email_address.email,
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'detail': 'Email verification failed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Http404:
            return Response(
                {'detail': 'Invalid or expired verification key.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': f'An error occurred during email verification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=["auth"])
class CookieTokenRefreshView(TokenRefreshView):
    """
    JWT refresh view that first looks for the refresh token in the request
    body and, if missing, falls back to the HttpOnly refresh cookie.
    """

    def _get_refresh_cookie_name(self) -> str:
        """
        Resolve the refresh cookie name from settings, preferring the
        dj-rest-auth style configuration while keeping a sensible default.
        """
        # dj-rest-auth legacy/global style
        cookie_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", None)

        # dj-rest-auth dict-style configuration (REST_AUTH / DJREST_AUTH)
        if not cookie_name:
            rest_auth_cfg = getattr(settings, "REST_AUTH", {}) or {}
            cookie_name = rest_auth_cfg.get("JWT_AUTH_REFRESH_COOKIE")

        if not cookie_name:
            djrest_auth_cfg = getattr(settings, "DJREST_AUTH", {}) or {}
            cookie_name = djrest_auth_cfg.get("JWT_AUTH_REFRESH_COOKIE")

        return cookie_name or "refresh"

    def post(self, request, *args, **kwargs):
        """
        Accepts:
        - `{"refresh": "<token>"}` in the JSON body (standard SimpleJWT behaviour), or
        - an HttpOnly cookie whose name is derived from configuration.
        """
        data = request.data.copy()

        if "refresh" not in data or not data.get("refresh"):
            cookie_name = self._get_refresh_cookie_name()
            refresh_from_cookie = request.COOKIES.get(cookie_name)
            if refresh_from_cookie:
                data["refresh"] = refresh_from_cookie

        serializer = self.get_serializer(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(tags=["auth"])
class ResendEmailVerificationView(APIView):
    """
    Resends email verification code to an unverified email address.
    Accepts either an explicit `email` in the payload or infers it from the
    authenticated user's account when the field is omitted.
    Only works for emails that are not yet verified.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ResendEmailCodeThrottle]

    def _build_serializer_payload(self, request):
        """
        dj-rest-auth's serializer expects an email field. Treat it as optional
        in the public API by falling back to the authenticated user when possible.
        """
        data = request.data.copy()
        has_email = bool(data.get('email'))

        if has_email:
            return data

        user = request.user if request.user.is_authenticated else None
        if user and user.email:
            data['email'] = user.email
            return data

        raise serializers.ValidationError(
            {'email': ['This field is required. Provide the email or authenticate a user with an email address.']}
        )

    def _cooldown_seconds(self):
        return getattr(settings, "ACCOUNT_EMAIL_VERIFICATION_RESEND_COOLDOWN", 60)

    def _cooldown_cache_key(self, email):
        return f"email-code-resend:{email}"

    def _cooldown_remaining(self, email):
        key = self._cooldown_cache_key(email)
        last_sent_at = cache.get(key)
        if not last_sent_at:
            return None
        elapsed = (timezone.now() - last_sent_at).total_seconds()
        remaining = int(self._cooldown_seconds() - elapsed)
        return remaining if remaining > 0 else None

    def _mark_cooldown(self, email):
        cache.set(self._cooldown_cache_key(email), timezone.now(), timeout=self._cooldown_seconds())

    @extend_schema(
        request=ResendEmailVerificationSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="ResendEmailCodeSuccess",
                    fields={'detail': serializers.CharField()},
                ),
                description="Verification code was (or will be) sent",
            ),
            400: OpenApiResponse(
                response=inline_serializer(
                    name="ResendEmailCodeError",
                    fields={'detail': serializers.CharField()},
                ),
                description="Invalid request or already verified email",
            ),
            429: OpenApiResponse(
                response=inline_serializer(
                    name="ResendEmailCodeThrottled",
                    fields={
                        'detail': serializers.CharField(),
                        'retry_in': serializers.IntegerField(required=False),
                    },
                ),
                description="Cooldown in effect",
            ),
            500: OpenApiResponse(
                response=inline_serializer(
                    name="ResendEmailCodeServerError",
                    fields={'detail': serializers.CharField()},
                ),
                description="Unexpected server error",
            ),
        },
        tags=["auth"],
        examples=[
            OpenApiExample(
                name="Resend Success",
                value={'detail': 'Verification code has been sent to your email.'},
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                name="Cooldown Active",
                value={'detail': 'Please wait before requesting another verification code.', 'retry_in': 25},
                response_only=True,
                status_codes=["429"],
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        if not allauth_account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
            return Response(
                {'detail': 'Code verification is not enabled.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payload = self._build_serializer_payload(request)
        serializer = ResendEmailVerificationSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        logger.info(
            "Email verification resend requested",
            extra={"email": email, "authenticated": request.user.is_authenticated},
        )
        try:
            email_address = EmailAddress.objects.get(email=email)
        except EmailAddress.DoesNotExist:
            return Response(
                {'detail': 'If this email is registered and unverified, a verification code has been sent.'},
                status=status.HTTP_200_OK
            )
        if email_address.verified:
            logger.info("Resend skipped because email already verified", extra={"email": email})
            return Response(
                {'detail': 'This email address is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email_address.user:
            return Response(
                {'detail': 'If this email is registered and unverified, a verification code has been sent.'},
                status=status.HTTP_200_OK
            )
        cooldown_remaining = self._cooldown_remaining(email)
        if cooldown_remaining:
            logger.warning(
                "Resend called during cooldown",
                extra={"email": email, "retry_in": cooldown_remaining},
            )
            return Response(
                {
                    'detail': 'Please wait before requesting another verification code.',
                    'retry_in': cooldown_remaining,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            old_process = EmailVerificationProcess.resume(request)
            if old_process:
                old_process.abort()
                logger.info(
                    "Aborted previous verification process before resend",
                    extra={"email": email}
                )
            
            try:
                confirmation = EmailConfirmation.create(
                    email_address=email_address
                )
                confirmation.sent = None
                confirmation.save()
            except Exception as e:
                logger.warning(f"Failed to create EmailConfirmation record on initiate: {str(e)}")
            
            process = EmailVerificationProcess.initiate(
                request=request,
                user=email_address.user,
                email=email_address.email,
            )
            
            if process and process.did_send:
                send_timestamp = timezone.now()
                _persist_confirmation_metadata(email_address, send_timestamp)
                self._mark_cooldown(email)
                logger.info("Verification code resent", extra={"email": email})
                return Response(
                    {'detail': 'Verification code has been sent to your email.'},
                    status=status.HTTP_200_OK
                )
            else:
                logger.error("Email verification process did not send code", extra={"email": email})
                return Response(
                    {'detail': 'Failed to send verification code. Please try again later.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error while sending verification code for %s", email)
            return Response(
                {'detail': f'An error occurred while sending verification code: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=["auth"])
class CustomLoginView(BaseLoginView):
    """
    Custom login view that uses CustomLoginSerializer to allow login
    with either username or email in the 'username' field.
    """
    serializer_class = CustomLoginSerializer
    
    @extend_schema(
        request=CustomLoginSerializer,
        responses={200: serializers.Serializer()},
        description="Login with username or email. Enter either username or email in the 'username' field.",
        tags=["auth"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Users"])
class UserViewset(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if getattr(self, 'action', None) in ['create','list']:
            return [permissions.AllowAny()]
        return [permission() for permission in self.permission_classes]

@extend_schema(tags=["auth"])
class CustomUserDetailsView(UserDetailsView):
    """
    Custom user details view that only allows PATCH and GET methods.
    PUT method is disabled to ensure consistent API behavior.
    """
    
    http_method_names = ['get', 'patch', 'head', 'options']
    
    @extend_schema(
        description="Get current user details",
        responses={200: UserSerializer},
        tags=["auth"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        description="Update current user details (partial update only)",
        request=UserSerializer,
        responses={200: UserSerializer},
        tags=["auth"]
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
