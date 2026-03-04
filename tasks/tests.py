from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category

from .models import Task

User = get_user_model()


class TaskViewNoPaginationTests(APITestCase):
    """Tests verifying that parent/me, volunteer/me, and available endpoints
    return ALL results without pagination truncation."""

    def setUp(self):
        self.parent = User.objects.create_user(
            username="parent1",
            email="parent1@example.com",
            password="TestPass123!",
            role="parent",
        )
        self.babysitter = User.objects.create_user(
            username="sitter1",
            email="sitter1@example.com",
            password="TestPass123!",
            role="babysitter",
        )
        self.category = Category.objects.create(name="General", is_active=True)

    def _create_tasks(self, count, user, **overrides):
        tasks = []
        for i in range(count):
            tasks.append(
                Task.objects.create(
                    user=user,
                    category=self.category,
                    title=f"Task {i + 1}",
                    description=f"Description {i + 1}",
                    start=timezone.now() + timezone.timedelta(days=i),
                    **overrides,
                )
            )
        return tasks

    def test_parent_me_returns_all_tasks_beyond_page_size(self):
        """Parent /tasks/parent/me/ must return all tasks even when count > PAGE_SIZE (20)."""
        self._create_tasks(25, self.parent)

        self.client.force_authenticate(user=self.parent)
        response = self.client.get("/api/tasks/parent/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 25)

    def test_volunteer_me_returns_all_tasks_beyond_page_size(self):
        """Babysitter /tasks/volunteer/me/ must return all assigned tasks even when count > PAGE_SIZE."""
        tasks = self._create_tasks(25, self.parent, volunteer=self.babysitter, status="claimed")

        self.client.force_authenticate(user=self.babysitter)
        response = self.client.get("/api/tasks/volunteer/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 25)

    def test_available_returns_all_tasks_beyond_page_size(self):
        """Babysitter /tasks/available/ must return all unclaimed tasks even when count > PAGE_SIZE."""
        self._create_tasks(25, self.parent)

        self.client.force_authenticate(user=self.babysitter)
        response = self.client.get("/api/tasks/available/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 25)
