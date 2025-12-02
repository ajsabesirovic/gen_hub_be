from types import SimpleNamespace
from unittest.mock import patch

from allauth.account.forms import (
    default_token_generator as allauth_token_generator,
)
from allauth.account.models import EmailAddress
from allauth.account.utils import user_pk_to_url_str
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class AuthRoutesTests(APITestCase):
    def setUp(self):
        self.password = 'StrongPass123!'
        self.user = User.objects.create_user(
            username='volunteer',
            email='volunteer@example.com',
            password=self.password,
            role='volunteer',
        )
        self.email_address = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True,
        )
        self.login_url = reverse('rest_login')
        self.logout_url = reverse('rest_logout')
        self.user_url = reverse('rest_user_details')
        self.password_reset_url = reverse('rest_password_reset')
        self.password_change_url = reverse('rest_password_change')
        self.token_refresh_url = reverse('token_refresh')
        self.token_verify_url = reverse('token_verify')
        self.register_url = reverse('rest_register')
        self.resend_email_url = reverse('rest_resend_email')
        self.verify_email_url = reverse('account_email_verification_sent')

    def _login(self):
        return self.client.post(
            self.login_url,
            {'username': self.user.username, 'password': self.password},
            format='json',
        )

    def test_registration_creates_user_and_stores_profile_fields(self):
        payload = {
            'username': 'new_volunteer',
            'email': 'new_volunteer@example.com',
            'password1': 'AnotherPass123!',
            'password2': 'AnotherPass123!',
            'name': 'New Volunteer',
            'role': 'volunteer',
        }
        response = self.client.post(self.register_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('detail', response.data)
        created_user = User.objects.get(username='new_volunteer')
        self.assertEqual(created_user.name, 'New Volunteer')
        self.assertEqual(created_user.role, 'volunteer')

    def test_login_returns_tokens_and_user_payload(self):
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], self.user.email)
        refresh_cookie = response.cookies.get('refresh')
        self.assertIsNotNone(refresh_cookie)
        self.assertTrue(refresh_cookie.value)

    def test_logout_with_valid_token_succeeds(self):
        login_response = self._login()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )
        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Successfully logged out.')

    def test_user_detail_patch_rejects_role_mutation_even_if_same_value(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.user_url, {'role': 'volunteer'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['role'][0], 'Role cannot be changed once set.'
        )

    def test_user_detail_patch_allows_other_profile_updates(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.user_url, {'city': 'Berlin'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['city'], 'Berlin')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_email_with_confirm_link(self):
        response = self.client.post(
            self.password_reset_url, {'email': self.user.email}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password/reset/confirm', mail.outbox[0].body)

    def test_password_reset_confirm_updates_password(self):
        uid = user_pk_to_url_str(self.user)
        token = allauth_token_generator.make_token(self.user)
        confirm_url = reverse(
            'password_reset_confirm', kwargs={'uidb64': uid, 'token': token}
        )
        payload = {
            'uid': uid,
            'token': token,
            'new_password1': 'BrandNewPass123!',
            'new_password2': 'BrandNewPass123!',
        }

        response = self.client.post(confirm_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass123!'))

    def test_password_change_endpoint_requires_correct_old_password(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'old_password': self.password,
            'new_password1': 'ShiftedPass123!',
            'new_password2': 'ShiftedPass123!',
        }
        response = self.client.post(
            self.password_change_url, payload, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ShiftedPass123!'))

    def test_token_refresh_and_verify_flow(self):
        login_response = self._login()
        refresh_cookie = login_response.cookies.get('refresh')
        self.assertIsNotNone(refresh_cookie)
        refresh_token = refresh_cookie.value

        refresh_response = self.client.post(
            self.token_refresh_url, {'refresh': refresh_token}, format='json'
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_access = refresh_response.data['access']

        verify_response = self.client.post(
            self.token_verify_url, {'token': new_access}, format='json'
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

    def test_resend_email_requires_payload_or_authenticated_user(self):
        response = self.client.post(self.resend_email_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_resend_email_uses_authenticated_user_email_when_missing(self):
        self.email_address.verified = False
        self.email_address.save(update_fields=['verified'])
        fake_process = SimpleNamespace(did_send=True)
        with patch('users.views.EmailVerificationProcess.initiate') as mock_init:
            mock_init.return_value = fake_process
            self.client.force_authenticate(user=self.user)

            response = self.client.post(self.resend_email_url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_init.assert_called_once()
        self.assertEqual(
            response.data['detail'], 'Verification code has been sent to your email.'
        )

    def test_resend_email_rejects_verified_addresses(self):
        self.email_address.verified = True
        self.email_address.save(update_fields=['verified'])
        payload = {'email': self.user.email}

        response = self.client.post(self.resend_email_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'], 'This email address is already verified.'
        )

    def test_verify_email_code_without_active_process_returns_error(self):
        response = self.client.post(
            self.verify_email_url, {'code': '123456'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_verify_email_creates_emailconfirmation_record(self):
        """Test that email verification creates EmailConfirmation record in database."""
        from allauth.account.models import EmailConfirmation
        
        self.email_address.verified = False
        self.email_address.save(update_fields=['verified'])
        
        def finish_verification():
            self.email_address.verified = True
            self.email_address.save(update_fields=['verified'])
            return self.email_address
        
        fake_process = SimpleNamespace(
            did_send=True,
            code='123456',
            max_attempts=5,
            attempts=0,
            email=self.email_address.email,
            is_valid=lambda: True,
            finish=finish_verification,
            record_invalid_attempt=lambda: None,
            abort=lambda: None,
        )
        
        with patch('users.views.EmailVerificationProcess.initiate') as mock_init, \
             patch('users.views.EmailVerificationProcess.resume') as mock_resume, \
             patch('users.views.compare_user_code', return_value=True):
            mock_init.return_value = fake_process
            mock_resume.return_value = fake_process
            
            self.client.post(self.resend_email_url, {'email': self.user.email}, format='json')
            
            response = self.client.post(
                self.verify_email_url, {'code': '123456'}, format='json'
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK, 
                        f"Response data: {response.data}")
        
        confirmations = EmailConfirmation.objects.filter(
            email_address=self.email_address
        )
        self.assertGreater(confirmations.count(), 0, 
                          "EmailConfirmation record should be created after verification")
