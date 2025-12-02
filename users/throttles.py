from rest_framework.throttling import SimpleRateThrottle


class _EmailVerificationThrottle(SimpleRateThrottle):
    """
    Base throttle that prefers user identity when authenticated and falls back
    to the caller's IP address otherwise.
    """

    scope = None 
    

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"user-{request.user.pk}"
        else:
            ident = f"ip-{self.get_ident(request)}"

        return self.cache_format % {"scope": self.scope, "ident": ident}


class VerifyEmailCodeThrottle(_EmailVerificationThrottle):
    scope = "verify_email_code"


class ResendEmailCodeThrottle(_EmailVerificationThrottle):
    scope = "resend_email_code"

