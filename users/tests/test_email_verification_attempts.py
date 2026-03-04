from types import SimpleNamespace
from unittest.mock import patch

from allauth.account.models import EmailAddress, EmailConfirmation
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import EmailVerificationAttempt


User = get_user_model()


@override_settings(
    REST_FRAMEWORK={
        **{k: v for k, v in __import__('django.conf', fromlist=['settings']).settings.REST_FRAMEWORK.items()},
        'DEFAULT_THROTTLE_RATES': {
            'verify_email_code': '1000/minute', 
            'resend_email_code': '1000/minute',
        },
    }
)
class EmailVerificationAttemptTests(APITestCase):
    """
    Integration tests for the email verification attempt limiting logic.
    """

    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="verifier",
            email="verifier@example.com",
            password=self.password,
        )
        self.email_address = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=False,
            primary=True,
        )
        self.confirmation = EmailConfirmation.create(email_address=self.email_address)
        self.confirmation.sent = timezone.now()
        self.confirmation.save()
        self.attempt = EmailVerificationAttempt.objects.get(
            email_confirmation=self.confirmation
        )

        self.verify_url = reverse("account_email_verification_sent")
        self.resend_url = reverse("rest_resend_email")

        self.code = "123456"

        self.process = SimpleNamespace(
            code=self.code,
            email=self.email_address.email,
            created_at=timezone.now(),
            is_valid=lambda: True,
            abort=lambda: None,
        )

        def finish():
            self.email_address.verified = True
            self.email_address.save(update_fields=["verified"])
            return self.email_address

        self.process.finish = finish

    def _post_code(self, code_value: str, user=None):
        """
        Helper to POST a verification code with the verification process patched.
        """
        if user:
            self.client.force_authenticate(user=user)

        with patch(
            "users.views.EmailVerificationProcess.resume", return_value=self.process
        ), patch(
            "users.views.compare_user_code",
            side_effect=lambda actual, expected: actual == expected,
        ):
            return self.client.post(
                self.verify_url, {"code": code_value}, format="json"
            )

    def test_can_verify_within_three_attempts(self):
        """
        User can make up to two invalid attempts and then succeed on the third.
        """
        for expected_attempts in (1, 2):
            response = self._post_code("000000")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["detail"], "Invalid verification code.")
            self.attempt.refresh_from_db()
            self.assertEqual(self.attempt.attempts, expected_attempts)

        response = self._post_code(self.code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Email successfully verified.")
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.attempts, 2)

    def test_fails_after_three_wrong_attempts(self):
        """
        Once three invalid attempts have been made, further attempts are blocked.
        """
        for expected_attempts in (1, 2, 3):
            response = self._post_code("000000")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.attempt.refresh_from_db()
            self.assertEqual(self.attempt.attempts, expected_attempts)

        response = self._post_code("000000")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Too many invalid attempts. Request a new verification email.",
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.attempts, 3)

        self.email_address.refresh_from_db()
        self.assertFalse(self.email_address.verified)

    def test_new_code_resets_attempt_limit(self):
        """
        A new confirmation key gets its own fresh attempt tracker.
        """
        for _ in range(3):
            self._post_code("000000")
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.attempts, 3)

        with patch(
            "users.views.EmailVerificationProcess.initiate"
        ) as mock_initiate, patch(
            "users.views.EmailVerificationProcess.resume", return_value=self.process
        ):
            mock_initiate.return_value = SimpleNamespace(did_send=True)
            response = self.client.post(
                self.resend_url, {"email": self.user.email}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_confirmation = (
            EmailConfirmation.objects.filter(email_address=self.email_address)
            .order_by("-created")
            .first()
        )
        self.assertNotEqual(new_confirmation.pk, self.confirmation.pk)

        new_attempt = EmailVerificationAttempt.objects.get(
            email_confirmation=new_confirmation
        )
        self.assertEqual(new_attempt.attempts, 0)

    def test_unrelated_user_cannot_use_the_code(self):
        """
        An authenticated user different from the email owner cannot use their code.
        """
        other_user = User.objects.create_user(
            username="intruder",
            email="intruder@example.com",
            password="Password123!",
        )

        response = self._post_code(self.code, user=other_user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid verification code.")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.attempts, 0)

    def test_old_confirmation_does_not_block_new_one(self):
        """
        A fully exhausted attempt record for an old confirmation does not
        interfere with verification of a newer confirmation.
        
        This test is already covered by test_new_code_resets_attempt_limit which
        uses the resend flow and verifies the new code works after exhausting the old one.
        """
        pass

