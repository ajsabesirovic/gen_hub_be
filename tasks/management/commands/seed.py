"""
Django management command to seed the database with initial demo data.

Usage:
    python manage.py seed
    python manage.py seed --flush
"""

from datetime import datetime, timedelta
from random import choice, randint, sample

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.models import Application
from availability.models import UserAvailability
from categories.models import Category
from notifications.models import Notification
from reviews.models import Review
from tasks.models import Task

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with initial demo data. Use --flush to remove seeded data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all seeded data instead of creating it",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.flush_data()
        else:
            self.seed_data()

    def flush_data(self):
        """Delete all seeded data."""
        self.stdout.write(self.style.WARNING("Flushing seeded data..."))

        deleted_counts = {
            "reviews": Review.objects.all().delete()[0],
            "notifications": Notification.objects.all().delete()[0],
            "applications": Application.objects.all().delete()[0],
            "tasks": Task.objects.all().delete()[0],
            "availabilities": UserAvailability.objects.all().delete()[0],
            "categories": Category.objects.all().delete()[0],
        }

        test_users = User.objects.filter(
            username__in=[
                "test_volunteer1",
                "test_volunteer2",
                "test_volunteer3",
                "test_senior1",
                "test_senior2",
            ]
        )
        deleted_counts["test_users"] = test_users.count()
        test_users.delete()

        self.stdout.write(self.style.SUCCESS("\n✓ Flushed seeded data:"))
        for model_name, count in deleted_counts.items():
            self.stdout.write(f"  - {model_name}: {count} deleted")

    def seed_data(self):
        """Create seed data for all models."""
        self.stdout.write(self.style.SUCCESS("Starting database seeding...\n"))

        categories = self.create_categories()
        volunteers, seniors = self.create_test_users()
        tasks = self.create_tasks(volunteers, seniors, categories)
        applications = self.create_applications(tasks, volunteers)
        availabilities = self.create_availabilities(volunteers + seniors)
        reviews = self.create_reviews(tasks, seniors, volunteers)
        notifications = self.create_notifications(volunteers + seniors)
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("✓ Database seeding completed!"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"\nCreated:")
        self.stdout.write(f"  - Categories: {len(categories)}")
        self.stdout.write(f"  - Test Users: {len(volunteers) + len(seniors)}")
        self.stdout.write(f"    • Volunteers: {len(volunteers)}")
        self.stdout.write(f"    • Seniors: {len(seniors)}")
        self.stdout.write(f"  - Tasks: {len(tasks)}")
        self.stdout.write(f"  - Applications: {len(applications)}")
        self.stdout.write(f"  - Availabilities: {len(availabilities)}")
        self.stdout.write(f"  - Reviews: {len(reviews)}")
        self.stdout.write(f"  - Notifications: {len(notifications)}")

    def create_categories(self):
        """Create seed categories."""
        self.stdout.write("Creating categories...")

        category_data = [
            {
                "name": "Grocery Shopping",
                "description": "Help with grocery shopping and errands",
            },
            {
                "name": "Home Maintenance",
                "description": "Assistance with household repairs and maintenance",
            },
            {
                "name": "Technology Support",
                "description": "Help with computers, phones, and other devices",
            },
            {
                "name": "Transportation",
                "description": "Rides to appointments, shopping, or social events",
            },
            {
                "name": "Companionship",
                "description": "Social visits, conversation, and companionship",
            },
            {
                "name": "Medical Appointments",
                "description": "Accompanying to doctor visits and medical care",
            },
            {
                "name": "Meal Preparation",
                "description": "Cooking meals and meal planning assistance",
            },
            {
                "name": "Pet Care",
                "description": "Walking pets, feeding, and basic pet care",
            },
            {
                "name": "Garden & Yard Work",
                "description": "Help with gardening, lawn care, and outdoor maintenance",
            },
            {
                "name": "Administrative Tasks",
                "description": "Help with paperwork, bills, and administrative work",
            },
        ]

        categories = []
        for data in category_data:
            category, created = Category.objects.get_or_create(
                name=data["name"], defaults=data
            )
            categories.append(category)
            if created:
                self.stdout.write(f"  ✓ Created category: {category.name}")

        return categories

    def create_test_users(self):
        """Create test users (volunteers and seniors)."""
        self.stdout.write("\nCreating test users...")

        volunteers_data = [
            {
                "username": "test_volunteer1",
                "email": "volunteer1@example.com",
                "name": "Emma Johnson",
                "age": "25",
                "phone": "+1-555-0101",
                "city": "New York",
                "country": "USA",
                "skills": "Grocery shopping, companionship, technology support",
                "role": "volunteer",
            },
            {
                "username": "test_volunteer2",
                "email": "volunteer2@example.com",
                "name": "Michael Chen",
                "age": "28",
                "phone": "+1-555-0102",
                "city": "Los Angeles",
                "country": "USA",
                "skills": "Home maintenance, transportation, pet care",
                "role": "volunteer",
            },
            {
                "username": "test_volunteer3",
                "email": "volunteer3@example.com",
                "name": "Sarah Williams",
                "age": "22",
                "phone": "+1-555-0103",
                "city": "Chicago",
                "country": "USA",
                "skills": "Meal preparation, garden work, administrative tasks",
                "role": "volunteer",
            },
        ]

        seniors_data = [
            {
                "username": "test_senior1",
                "email": "senior1@example.com",
                "name": "Robert Anderson",
                "age": "72",
                "phone": "+1-555-0201",
                "city": "New York",
                "country": "USA",
                "skills": "Retired teacher, needs help with technology",
                "role": "senior",
            },
            {
                "username": "test_senior2",
                "email": "senior2@example.com",
                "name": "Margaret Thompson",
                "age": "68",
                "phone": "+1-555-0202",
                "city": "Los Angeles",
                "country": "USA",
                "skills": "Retired nurse, needs transportation assistance",
                "role": "senior",
            },
        ]

        volunteers = []
        for data in volunteers_data:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={**data, "password": "pbkdf2_sha256$test"},
            )
            if created:
                user.set_password("testpass123")
                user.save()
                self.stdout.write(f"  ✓ Created volunteer: {user.username} ({user.name})")
            volunteers.append(user)

        seniors = []
        for data in seniors_data:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={**data, "password": "pbkdf2_sha256$test"},
            )
            if created:
                user.set_password("testpass123")
                user.save()
                self.stdout.write(f"  ✓ Created senior: {user.username} ({user.name})")
            seniors.append(user)

        return volunteers, seniors

    def create_tasks(self, volunteers, seniors, categories):
        """Create seed tasks."""
        self.stdout.write("\nCreating tasks...")

        if not seniors:
            self.stdout.write(self.style.WARNING("  ⚠ No seniors found, skipping tasks"))
            return []

        task_templates = [
            {
                "title": "Weekly Grocery Shopping",
                "description": "Need help with weekly grocery shopping at the local supermarket. Prefer morning hours.",
                "duration": 120,
                "location": "Local Supermarket, Main Street",
            },
            {
                "title": "Computer Setup Help",
                "description": "Need assistance setting up a new laptop and learning basic computer skills.",
                "duration": 180,
                "location": "Home",
            },
            {
                "title": "Doctor Appointment Transportation",
                "description": "Need a ride to the doctor's office for a regular checkup.",
                "duration": 90,
                "location": "Medical Center, Oak Avenue",
            },
            {
                "title": "Garden Cleanup",
                "description": "Help needed with fall garden cleanup and preparing for winter.",
                "duration": 240,
                "location": "Home Garden",
            },
            {
                "title": "Meal Preparation",
                "description": "Assistance with preparing meals for the week ahead.",
                "duration": 150,
                "location": "Home Kitchen",
            },
            {
                "title": "Pet Walking",
                "description": "Daily dog walking service needed while recovering from surgery.",
                "duration": 30,
                "location": "Neighborhood",
            },
            {
                "title": "Home Repair - Leaky Faucet",
                "description": "Kitchen faucet is leaking, need help fixing it.",
                "duration": 60,
                "location": "Home",
            },
            {
                "title": "Companionship Visit",
                "description": "Looking for someone to visit and chat, maybe play some board games.",
                "duration": 120,
                "location": "Home",
            },
            {
                "title": "Bill Organization",
                "description": "Help organizing and paying monthly bills online.",
                "duration": 90,
                "location": "Home",
            },
            {
                "title": "Pharmacy Pickup",
                "description": "Need someone to pick up prescription medications from the pharmacy.",
                "duration": 45,
                "location": "City Pharmacy, Park Street",
            },
        ]

        tasks = []
        now = timezone.now()
        colors = ["#0099ff", "#ff6b6b", "#4ecdc4", "#45b7d1", "#f9ca24", "#6c5ce7"]

        for i, template in enumerate(task_templates):
            senior = choice(seniors)
            category = choice(categories)
            days_offset = randint(-30, 30)
            start_time = now + timedelta(days=days_offset, hours=randint(9, 17))
            end_time = start_time + timedelta(minutes=template["duration"])
            status = choice([Task.UNCLAIMED, Task.CLAIMED])
            volunteer = choice(volunteers) if status == Task.CLAIMED and volunteers else None

            task = Task.objects.create(
                user=senior,
                volunteer=volunteer,
                category=category,
                title=template["title"],
                description=template["description"],
                start=start_time,
                end=end_time,
                whole_day=False,
                color=choice(colors),
                location=template["location"],
                status=status,
                duration=template["duration"],
                extra_dates={},
            )
            tasks.append(task)
            self.stdout.write(f"  ✓ Created task: {task.title} ({task.status})")

        return tasks

    def create_applications(self, tasks, volunteers):
        """Create seed applications."""
        self.stdout.write("\nCreating applications...")

        if not tasks or not volunteers:
            self.stdout.write(
                self.style.WARNING("  ⚠ No tasks or volunteers found, skipping applications")
            )
            return []

        applications = []
        unclaimed_tasks = [t for t in tasks if t.status == Task.UNCLAIMED]

        for task in sample(unclaimed_tasks, min(5, len(unclaimed_tasks))):
            num_applications = randint(1, min(3, len(volunteers)))
            task_volunteers = sample(volunteers, num_applications)

            for volunteer in task_volunteers:
                if not Application.objects.filter(task=task, volunteer=volunteer).exists():
                    status = choice(
                        [Application.PENDING, Application.ACCEPTED, Application.REJECTED]
                    )
                    application = Application.objects.create(
                        task=task, volunteer=volunteer, status=status
                    )
                    applications.append(application)
                    self.stdout.write(
                        f"  ✓ Created application: {volunteer.username} -> {task.title} ({status})"
                    )

        return applications

    def create_availabilities(self, users):
        """Create seed availability records."""
        self.stdout.write("\nCreating availabilities...")

        if not users:
            self.stdout.write(self.style.WARNING("  ⚠ No users found, skipping availabilities"))
            return []

        availabilities = []
        days_of_week = list(range(7))

        for user in users:
            num_records = randint(2, 4)

            for _ in range(num_records):
                avail_type = choice([UserAvailability.WEEKLY, UserAvailability.MONTHLY])
                now = timezone.now()

                if avail_type == UserAvailability.WEEKLY:
                    day_of_week = choice(days_of_week)
                    days_ahead = (day_of_week - now.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    start_time = now + timedelta(days=days_ahead, hours=randint(9, 16))
                    end_time = start_time + timedelta(hours=randint(2, 4))
                    date = None
                else:
                    day_of_week = None
                    days_ahead = randint(1, 30)
                    start_time = now + timedelta(days=days_ahead, hours=randint(9, 16))
                    end_time = start_time + timedelta(hours=randint(2, 6))
                    date = start_time

                availability = UserAvailability.objects.create(
                    user=user,
                    type=avail_type,
                    day_of_week=day_of_week,
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                )
                availabilities.append(availability)
                self.stdout.write(
                    f"  ✓ Created availability: {user.username} ({avail_type})"
                )

        return availabilities

    def create_reviews(self, tasks, seniors, volunteers):
        """Create seed reviews."""
        self.stdout.write("\nCreating reviews...")

        if not tasks or not seniors or not volunteers:
            self.stdout.write(
                self.style.WARNING("  ⚠ Missing required data, skipping reviews")
            )
            return []

        reviews = []
        claimed_tasks = [t for t in tasks if t.status == Task.CLAIMED and t.volunteer]

        review_comments = [
            "Excellent work! Very helpful and professional.",
            "Great communication and punctuality. Highly recommend!",
            "Very kind and patient. Made the whole process easy.",
            "Outstanding service. Would definitely request help again.",
            "Very reliable and went above and beyond expectations.",
            "Professional and courteous. Great experience overall.",
            "Helpful and efficient. Completed the task perfectly.",
            "Very friendly and understanding. Made me feel comfortable.",
        ]

        for task in sample(claimed_tasks, min(3, len(claimed_tasks))):
            if not hasattr(task, "review"):
                senior = task.user
                volunteer = task.volunteer

                review = Review.objects.create(
                    task=task,
                    senior=senior,
                    volunteer=volunteer,
                    rating=randint(4, 5),
                    comment=choice(review_comments),
                )
                reviews.append(review)
                self.stdout.write(
                    f"  ✓ Created review: {senior.username} -> {volunteer.username} ({review.rating} stars)"
                )

        return reviews

    def create_notifications(self, users):
        """Create seed notifications."""
        self.stdout.write("\nCreating notifications...")

        if not users:
            self.stdout.write(self.style.WARNING("  ⚠ No users found, skipping notifications"))
            return []

        notifications = []
        notification_templates = [
            {
                "type": "task_created",
                "title": "New Task Available",
                "message": "A new task matching your skills has been posted.",
            },
            {
                "type": "application_accepted",
                "title": "Application Accepted",
                "message": "Your application for 'Weekly Grocery Shopping' has been accepted!",
            },
            {
                "type": "application_rejected",
                "title": "Application Status",
                "message": "Your application for 'Garden Cleanup' was not selected.",
            },
            {
                "type": "task_reminder",
                "title": "Task Reminder",
                "message": "You have a task scheduled for tomorrow at 10:00 AM.",
            },
            {
                "type": "review_received",
                "title": "New Review",
                "message": "You received a 5-star review from Robert Anderson!",
            },
            {
                "type": "message",
                "title": "New Message",
                "message": "You have a new message from a senior citizen.",
            },
        ]

        for user in users:
            num_notifications = randint(2, 5)
            user_notifications = sample(notification_templates, num_notifications)

            for template in user_notifications:
                is_read = choice([True, False])
                notification = Notification.objects.create(
                    user=user,
                    type=template["type"],
                    title=template["title"],
                    message=template["message"],
                    is_read=is_read,
                )
                notifications.append(notification)
                self.stdout.write(
                    f"  ✓ Created notification: {user.username} - {notification.title}"
                )

        return notifications

