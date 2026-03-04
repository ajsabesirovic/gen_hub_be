from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from users.models import ParentProfile, VolunteerProfile

User = get_user_model()


class ProfileSignalTests(TestCase):
    """Test automatic profile creation via signals."""
    
    def test_parent_profile_created_on_user_creation(self):
        """Parent profile should be created automatically when parent user is created."""
        user = User.objects.create_user(
            username='parent1',
            email='parent1@example.com',
            password='testpass123',
            role='parent'
        )
        
        self.assertTrue(hasattr(user, 'parent_profile'))
        self.assertIsNotNone(user.parent_profile)
        self.assertEqual(user.parent_profile.user, user)
    
    def test_volunteer_profile_created_on_user_creation(self):
        """Volunteer profile should be created automatically when volunteer user is created."""
        user = User.objects.create_user(
            username='volunteer1',
            email='volunteer1@example.com',
            password='testpass123',
            role='volunteer'
        )
        
        self.assertTrue(hasattr(user, 'volunteer_profile'))
        self.assertIsNotNone(user.volunteer_profile)
        self.assertEqual(user.volunteer_profile.user, user)
    
    def test_admin_no_profile_created(self):
        """Admin users should not get profiles."""
        admin = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='testpass123',
            is_staff=True
        )
        
        self.assertFalse(hasattr(admin, 'parent_profile'))
        self.assertFalse(hasattr(admin, 'volunteer_profile'))
        
        parent_profile_count = ParentProfile.objects.filter(user=admin).count()
        volunteer_profile_count = VolunteerProfile.objects.filter(user=admin).count()
        
        self.assertEqual(parent_profile_count, 0)
        self.assertEqual(volunteer_profile_count, 0)
    
    def test_superuser_no_profile_created(self):
        """Superuser should not get profiles."""
        superuser = User.objects.create_superuser(
            username='super1',
            email='super1@example.com',
            password='testpass123'
        )
        
        parent_profile_count = ParentProfile.objects.filter(user=superuser).count()
        volunteer_profile_count = VolunteerProfile.objects.filter(user=superuser).count()
        
        self.assertEqual(parent_profile_count, 0)
        self.assertEqual(volunteer_profile_count, 0)
    
    def test_user_without_role_no_profile_created(self):
        """Users without a role should not get profiles."""
        user = User.objects.create_user(
            username='norole1',
            email='norole1@example.com',
            password='testpass123'
        )
        
        parent_profile_count = ParentProfile.objects.filter(user=user).count()
        volunteer_profile_count = VolunteerProfile.objects.filter(user=user).count()
        
        self.assertEqual(parent_profile_count, 0)
        self.assertEqual(volunteer_profile_count, 0)


class ParentProfileAPITests(TestCase):
    """Test Parent Profile API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.parent_user = User.objects.create_user(
            username='parent1',
            email='parent1@example.com',
            password='testpass123',
            role='parent',
            name='Parent One'
        )
        
        self.volunteer_user = User.objects.create_user(
            username='volunteer1',
            email='volunteer1@example.com',
            password='testpass123',
            role='volunteer'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='testpass123',
            is_staff=True
        )
    
    def test_parent_can_access_own_profile(self):
        """Parent user should be able to access their own profile."""
        self.client.force_authenticate(user=self.parent_user)
        response = self.client.get('/api/users/profile/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['user']), str(self.parent_user.id))
        self.assertEqual(response.data['user_email'], self.parent_user.email)
    
    def test_parent_can_update_own_profile(self):
        """Parent user should be able to update their own profile."""
        self.client.force_authenticate(user=self.parent_user)
        
        data = {
            'street': '123 Main St',
            'house_number': '456',
            'medical_notes': 'Some medical notes',
            'emergency_contact': 'John Doe - 555-1234'
        }
        
        response = self.client.patch('/api/users/profile/parent/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['street'], '123 Main St')
        self.assertEqual(response.data['house_number'], '456')
        
        self.parent_user.parent_profile.refresh_from_db()
        self.assertEqual(self.parent_user.parent_profile.street, '123 Main St')
    
    def test_volunteer_cannot_access_parent_profile(self):
        """Volunteer user should not be able to access parent profile endpoint."""
        self.client.force_authenticate(user=self.volunteer_user)
        response = self.client.get('/api/users/profile/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_cannot_access_parent_profile(self):
        """Admin user should not be able to access parent profile endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/users/profile/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_unauthenticated_cannot_access_parent_profile(self):
        """Unauthenticated user should not be able to access parent profile."""
        response = self.client.get('/api/users/profile/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class VolunteerProfileAPITests(TestCase):
    """Test Volunteer Profile API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.volunteer_user = User.objects.create_user(
            username='volunteer1',
            email='volunteer1@example.com',
            password='testpass123',
            role='volunteer',
            name='Volunteer One'
        )
        
        self.parent_user = User.objects.create_user(
            username='parent1',
            email='parent1@example.com',
            password='testpass123',
            role='parent'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='testpass123',
            is_staff=True
        )
    
    def test_volunteer_can_access_own_profile(self):
        """Volunteer user should be able to access their own profile."""
        self.client.force_authenticate(user=self.volunteer_user)
        response = self.client.get('/api/users/profile/volunteer/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['user']), str(self.volunteer_user.id))
        self.assertEqual(response.data['user_email'], self.volunteer_user.email)
    
    def test_volunteer_can_update_own_profile(self):
        """Volunteer user should be able to update their own profile."""
        self.client.force_authenticate(user=self.volunteer_user)
        
        data = {
            'skills': 'Cooking, Driving, Gardening',
            'has_vehicle': True,
            'preferred_tasks': 'Transportation, Shopping'
        }
        
        response = self.client.patch('/api/users/profile/volunteer/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['skills'], 'Cooking, Driving, Gardening')
        self.assertTrue(response.data['has_vehicle'])
        
        self.volunteer_user.volunteer_profile.refresh_from_db()
        self.assertEqual(self.volunteer_user.volunteer_profile.skills, 'Cooking, Driving, Gardening')
        self.assertTrue(self.volunteer_user.volunteer_profile.has_vehicle)
    
    def test_parent_cannot_access_volunteer_profile(self):
        """Parent user should not be able to access volunteer profile endpoint."""
        self.client.force_authenticate(user=self.parent_user)
        response = self.client.get('/api/users/profile/volunteer/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_cannot_access_volunteer_profile(self):
        """Admin user should not be able to access volunteer profile endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/users/profile/volunteer/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_unauthenticated_cannot_access_volunteer_profile(self):
        """Unauthenticated user should not be able to access volunteer profile."""
        response = self.client.get('/api/users/profile/volunteer/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserRoleTests(TestCase):
    """Test User role constraints."""
    
    def test_role_choices_only_parent_and_volunteer(self):
        """Role field should only accept 'parent' or 'volunteer'."""
        parent = User.objects.create_user(
            username='parent1',
            email='parent1@example.com',
            password='testpass123',
            role='parent'
        )
        self.assertEqual(parent.role, 'parent')
        
        volunteer = User.objects.create_user(
            username='volunteer1',
            email='volunteer1@example.com',
            password='testpass123',
            role='volunteer'
        )
        self.assertEqual(volunteer.role, 'volunteer')
    
    def test_admin_identified_by_staff_flags(self):
        """Admins should be identified by is_staff and is_superuser, not role."""
        admin = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='testpass123',
            is_staff=True
        )
        
        self.assertTrue(admin.is_staff)
        self.assertIsNone(admin.role)
        
        superuser = User.objects.create_superuser(
            username='super1',
            email='super1@example.com',
            password='testpass123'
        )
        
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)

