import logging
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated, IsAdminUser
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
from rest_framework import generics, permissions, status, serializers, exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db import transaction
from django.db.models import Q

from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC, EmailAddress
from allauth.account import app_settings as allauth_account_settings
from allauth.account.internal.flows.email_verification import verify_email_and_resume
from allauth.account.internal.flows.email_verification_by_code import EmailVerificationProcess
from allauth.core.internal.cryptokit import compare_user_code
from dj_rest_auth.registration.serializers import ResendEmailVerificationSerializer
from dj_rest_auth.views import LoginView as BaseLoginView, UserDetailsView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from .models import ParentProfile, BabysitterProfile
from .serializers import (
    CustomLoginSerializer,
    ParentProfileSerializer,
    UserSerializer,
    UserWithProfileSerializer,
    BabysitterProfileSerializer,
    MeProfileSerializer,
)
from .admin_serializers import AdminUserListSerializer, AdminUserDetailSerializer
from .throttles import ResendEmailCodeThrottle, VerifyEmailCodeThrottle
from gen_hub_be.permissions import IsAdminUser

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
        cookie_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", None)

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


class PublicParentProfileSerializer(serializers.Serializer):
    """Serializer for public parent profile data (visible to babysitters)."""
    description = serializers.CharField(allow_null=True, required=False)
    number_of_children = serializers.IntegerField(allow_null=True, required=False)
    children_ages = serializers.ListField(child=serializers.CharField(), required=False)
    has_special_needs = serializers.BooleanField(required=False)
    special_needs_description = serializers.CharField(allow_null=True, required=False)
    preferred_babysitting_location = serializers.CharField(allow_null=True, required=False)
    preferred_languages = serializers.ListField(child=serializers.CharField(), required=False)
    preferred_experience_years = serializers.IntegerField(allow_null=True, required=False)
    preferred_experience_with_ages = serializers.ListField(child=serializers.CharField(), required=False)
    smoking_allowed = serializers.BooleanField(required=False)
    pets_in_home = serializers.BooleanField(required=False)


class PublicParentSerializer(serializers.ModelSerializer):
    """Serializer for public parent data (visible to babysitters)."""
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "city",
            "country",
            "profile_image",
            "role",
            "profile",
        )

    def get_profile(self, obj):
        if obj.role != "parent":
            return None
        profile = getattr(obj, "parent_profile", None)
        if not profile:
            return None
        return PublicParentProfileSerializer(profile).data


@extend_schema(tags=["Users"])
class UserViewset(ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if getattr(self, 'action', None) in ['create', 'list', 'by_username']:
            return [permissions.AllowAny()]
        return [permission() for permission in self.permission_classes]

    def _build_filters(self):
        params = self.request.query_params
        filters = {}

        role = params.get("role")
        if role:
            valid_roles = {choice[0] for choice in User.ROLE_CHOICES}
            if role not in valid_roles:
                raise serializers.ValidationError({"role": "Invalid role."})
            filters["role"] = role

        return filters

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "action", None) == "list":
            filters = self._build_filters()
            if filters:
                qs = qs.filter(**filters)
        return qs

    def get_serializer_class(self):
        if getattr(self, "action", None) == "list":
            role = self.request.query_params.get("role")
            if role == "babysitter":
                from .serializers import PublicBabysitterSerializer

                return PublicBabysitterSerializer
        if getattr(self, "action", None) == "by_username":
            return PublicParentSerializer
        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single user by ID with appropriate serializer based on their role.
        """
        instance = self.get_object()

        if instance.role == "babysitter":
            from .serializers import PublicBabysitterSerializer
            serializer = PublicBabysitterSerializer(instance, context={'request': request})
        elif instance.role == "parent":
            serializer = PublicParentSerializer(instance, context={'request': request})
        else:
            serializer = self.get_serializer(instance)

        return Response(serializer.data)

    @extend_schema(
        description="Get user by username. Returns public profile data.",
        responses={200: PublicParentSerializer},
    )
    @action(detail=False, methods=['get'], url_path='by-username/(?P<username>[^/.]+)')
    def by_username(self, request, username=None):
        """Fetch a user by username with their public profile."""
        try:
            user = User.objects.select_related('parent_profile', 'babysitter_profile').get(username=username)
        except User.DoesNotExist:
            raise Http404("User not found.")

        if user.role == "parent":
            serializer = PublicParentSerializer(user)
        elif user.role == "babysitter":
            from .serializers import PublicBabysitterSerializer
            serializer = PublicBabysitterSerializer(user)
        else:
            serializer = UserSerializer(user)

        return Response(serializer.data)

@extend_schema(tags=["auth"])
class CustomUserDetailsView(UserDetailsView):
    """
    Custom user details view that only allows PATCH and GET methods.
    PUT method is disabled to ensure consistent API behavior.
    """
    
    http_method_names = ['get', 'patch', 'head', 'options']
    serializer_class = UserWithProfileSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    @extend_schema(
        description="Get current user details",
        responses={200: UserWithProfileSerializer},
        tags=["auth"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        description="Update current user details (partial update only). ",
        request=UserWithProfileSerializer,
        responses={200: UserWithProfileSerializer},
        tags=["auth"]
    )
    def patch(self, request, *args, **kwargs):      
        data = request.data.copy()
        partial = True
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


@extend_schema(tags=["Profiles"])
class ParentProfileView(APIView):
    """
    Retrieve or update the parent profile for the authenticated user.
    Only accessible to users with role='parent'.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            raise exceptions.PermissionDenied("Admin users do not have profiles.")
        
        if user.role != 'parent':
            raise exceptions.PermissionDenied("Only parent users can access this profile.")
        
        try:
            return ParentProfile.objects.get(user=user)
        except ParentProfile.DoesNotExist:
            raise Http404("Parent profile not found.")
    
    @extend_schema(
        description="Get current user's parent profile",
        responses={200: ParentProfileSerializer},
    )
    def get(self, request):
        profile = self.get_object()
        serializer = ParentProfileSerializer(profile)
        return Response(serializer.data)
    
    @extend_schema(
        description="Update current user's parent profile",
        request=ParentProfileSerializer,
        responses={200: ParentProfileSerializer},
    )
    def patch(self, request):
        profile = self.get_object()
        serializer = ParentProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(tags=["Profiles"])
class BabysitterProfileView(APIView):
    """
    Retrieve or update the babysitter profile for the authenticated user.
    Only accessible to users with role='babysitter'.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            raise exceptions.PermissionDenied("Admin users do not have profiles.")
        
        if user.role != 'babysitter':
            raise exceptions.PermissionDenied("Only babysitter users can access this profile.")
        
        try:
            return BabysitterProfile.objects.get(user=user)
        except BabysitterProfile.DoesNotExist:
            raise Http404("Babysitter profile not found.")
    
    @extend_schema(
        description="Get current user's babysitter profile",
        responses={200: BabysitterProfileSerializer},
    )
    def get(self, request):
        profile = self.get_object()
        serializer = BabysitterProfileSerializer(profile)
        return Response(serializer.data)
    
    @extend_schema(
        description="Update current user's babysitter profile",
        request=BabysitterProfileSerializer,
        responses={200: BabysitterProfileSerializer},
    )
    def patch(self, request):
        profile = self.get_object()
        serializer = BabysitterProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(tags=["Profiles"])
class MeProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: MeProfileSerializer},
    )
    def get(self, request):
        user = request.user
        if user.is_staff or user.is_superuser:
            raise exceptions.PermissionDenied()
        serializer = MeProfileSerializer(user, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=MeProfileSerializer,
        responses={200: MeProfileSerializer},
    )
    def patch(self, request):
        user = request.user
        if user.is_staff or user.is_superuser:
            raise exceptions.PermissionDenied()
        with transaction.atomic():
            serializer = MeProfileSerializer(
                user,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(serializer.data)


@extend_schema(tags=["Admin"])
class AdminUserViewSet(ModelViewSet):
    """
    Admin-only ViewSet for managing all users.
    Allows admins to view, update, activate/deactivate, and delete users.
    """
    queryset = User.objects.all().select_related('parent_profile', 'babysitter_profile')
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AdminUserListSerializer
        return AdminUserDetailSerializer

    def get_queryset(self):
        """Filter users based on query parameters"""
        queryset = super().get_queryset()
        
        role = self.request.query_params.get('role')
        if role and role in ['parent', 'babysitter']:
            queryset = queryset.filter(role=role)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_admin = self.request.query_params.get('is_admin')
        if is_admin is not None:
            if is_admin.lower() == 'true':
                queryset = queryset.filter(Q(is_staff=True) | Q(is_superuser=True))
            else:
                queryset = queryset.filter(is_staff=False, is_superuser=False)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )
        
        return queryset.order_by('-date_joined')

    @extend_schema(
        description="Deactivate a user account",
        responses={200: AdminUserDetailSerializer},
    )
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a user account"""
        user = self.get_object()
        
        if user == request.user:
            return Response(
                {'detail': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if (user.is_staff or user.is_superuser) and user != request.user:
            return Response(
                {'detail': 'Cannot deactivate admin users.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @extend_schema(
        description="Activate a user account",
        responses={200: AdminUserDetailSerializer},
    )
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a user account"""
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Prevent deleting admin users"""
        if instance.is_staff or instance.is_superuser:
            raise exceptions.PermissionDenied("Cannot delete admin users.")
        instance.delete()
