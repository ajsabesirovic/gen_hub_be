"""
Django management command to seed specific models using existing users.

Usage:
    python manage.py seed_model categories
    python manage.py seed_model tasks --count 20
    python manage.py seed_model applications
    python manage.py seed_model invitations
    python manage.py seed_model availabilities
    python manage.py seed_model reviews
    python manage.py seed_model notifications
    python manage.py seed_model all

    # Flush specific models
    python manage.py seed_model categories --flush
    python manage.py seed_model tasks --flush
"""

from datetime import timedelta
from random import choice, randint, sample

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from applications.models import Application, Invitation
from availability.models import UserAvailability
from categories.models import Category
from notifications.models import Notification
from reviews.models import Review
from tasks.models import Task

User = get_user_model()

AVAILABLE_MODELS = [
    "categories",
    "tasks",
    "applications",
    "invitations",
    "availabilities",
    "reviews",
    "notifications",
    "all",
]


class Command(BaseCommand):
    help = "Seed a specific model with demo data using existing users."

    def add_arguments(self, parser):
        parser.add_argument(
            "model",
            type=str,
            choices=AVAILABLE_MODELS,
            help=f"Model to seed: {', '.join(AVAILABLE_MODELS)}",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of records to create (default: 10, applies to tasks)",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete data for the specified model instead of creating it",
        )

    def handle(self, *args, **options):
        model = options["model"]
        count = options["count"]
        flush = options["flush"]

        if flush:
            self.flush_model(model)
        else:
            self.seed_model(model, count)

    def flush_model(self, model):
        """Flush data for a specific model."""
        self.stdout.write(self.style.WARNING(f"Flushing {model}..."))

        model_map = {
            "categories": Category,
            "tasks": Task,
            "applications": Application,
            "invitations": Invitation,
            "availabilities": UserAvailability,
            "reviews": Review,
            "notifications": Notification,
        }

        if model == "all":
            order = ["reviews", "notifications", "invitations", "applications", "availabilities", "tasks", "categories"]
            for m in order:
                deleted = model_map[m].objects.all().delete()[0]
                self.stdout.write(f"  Deleted {deleted} {m}")
        else:
            deleted = model_map[model].objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {deleted} {model}"))

    def seed_model(self, model, count):
        """Seed data for a specific model."""
        babysitters = list(User.objects.filter(role="babysitter", is_active=True))
        parents = list(User.objects.filter(role="parent", is_active=True))

        if not parents and model not in ["categories"]:
            self.stdout.write(
                self.style.ERROR("✗ No parent users found! Create users first.")
            )
            return

        self.stdout.write(f"Found {len(parents)} parents and {len(babysitters)} babysitters\n")

        if model == "categories":
            self.seed_categories()
        elif model == "tasks":
            self.seed_tasks(babysitters, parents, count)
        elif model == "applications":
            self.seed_applications(babysitters)
        elif model == "invitations":
            self.seed_invitations(babysitters)
        elif model == "availabilities":
            self.seed_availabilities(babysitters + parents)
        elif model == "reviews":
            self.seed_reviews(parents, babysitters)
        elif model == "notifications":
            self.seed_notifications(babysitters + parents)
        elif model == "all":
            self.stdout.write(self.style.SUCCESS("Seeding all models..."))
            self.seed_categories()
            self.seed_tasks(babysitters, parents, count)
            self.seed_applications(babysitters)
            self.seed_invitations(babysitters)
            self.seed_availabilities(babysitters + parents)
            self.seed_reviews(parents, babysitters)
            self.seed_notifications(babysitters + parents)

    def seed_categories(self):
        """Seed categories."""
        self.stdout.write("Seeding categories...")

        category_data = [
            ("Regular Babysitting", "Standard babysitting for children of all ages"),
            ("Newborn Care", "Specialized care for infants and newborns"),
            ("After School Care", "Picking up children from school and supervising"),
            ("Overnight Care", "Babysitting that extends through the night"),
            ("Weekend Care", "Weekend babysitting services"),
            ("Special Needs Care", "Care for children with special needs"),
            ("Tutoring & Homework Help", "Helping children with homework"),
            ("Pet Care (with children)", "Taking care of children and pets"),
            ("Event Babysitting", "Babysitting for special events"),
            ("Emergency Care", "Last-minute or urgent babysitting"),
        ]

        created = 0
        for name, description in category_data:
            _, was_created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description, "is_active": True}
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} categories"))

    def seed_tasks(self, babysitters, parents, count):
        """Seed tasks."""
        self.stdout.write(f"Seeding {count} tasks...")

        categories = list(Category.objects.filter(is_active=True))
        if not categories:
            self.stdout.write(self.style.WARNING("  No categories! Run: python manage.py seed_model categories"))
            return

        task_templates = [
            ("Evening Babysitter Needed", "Looking for a reliable babysitter", 240, "123 Main Street"),
            ("After School Pickup", "Need someone for school pickup and care", 180, "Lincoln Elementary"),
            ("Weekend Date Night Sitter", "Sitter needed for Saturday night", 300, "456 Oak Avenue"),
            ("Infant Care - Daytime", "Experienced caregiver for 6-month-old", 480, "789 Maple Drive"),
            ("Overnight Babysitter", "Overnight care while we're out of town", 960, "321 Pine Street"),
            ("Last Minute Sitter Needed", "Emergency sitter for tomorrow", 180, "555 Elm Road"),
            ("Homework Help & Tutoring", "Help with math homework", 120, "777 Cedar Lane"),
            ("Newborn Night Nurse", "Night care for newborn", 480, "888 Birch Boulevard"),
            ("Summer Day Supervision", "Fun energetic sitter for summer", 360, "Home with pool"),
            ("Special Needs Care", "Experienced caregiver needed", 240, "999 Willow Way"),
        ]

        now = timezone.now()
        created = 0

        for i in range(count):
            title, desc, duration, location = task_templates[i % len(task_templates)]
            parent = choice(parents)
            category = choice(categories)
            start_time = now + timedelta(days=randint(-14, 30), hours=randint(7, 19))
            status = choice([Task.UNCLAIMED] * 5 + [Task.CLAIMED] * 3 + [Task.COMPLETED] * 2)
            volunteer = choice(babysitters) if status != Task.UNCLAIMED and babysitters else None

            Task.objects.create(
                user=parent,
                volunteer=volunteer,
                category=category,
                title=title,
                description=desc,
                start=start_time,
                end=start_time + timedelta(minutes=duration),
                location=location,
                status=status,
                duration=duration,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} tasks"))

    def seed_applications(self, babysitters):
        """Seed applications on unclaimed tasks."""
        self.stdout.write("Seeding applications...")

        if not babysitters:
            self.stdout.write(self.style.WARNING("  No babysitters found"))
            return

        unclaimed_tasks = list(Task.objects.filter(status=Task.UNCLAIMED))
        if not unclaimed_tasks:
            self.stdout.write(self.style.WARNING("  No unclaimed tasks"))
            return

        created = 0
        for task in sample(unclaimed_tasks, min(len(unclaimed_tasks), len(unclaimed_tasks) // 2 + 1)):
            for babysitter in sample(babysitters, min(len(babysitters), randint(1, 3))):
                if not Application.objects.filter(task=task, volunteer=babysitter).exists():
                    Application.objects.create(
                        task=task,
                        volunteer=babysitter,
                        status=choice([Application.PENDING] * 3 + [Application.ACCEPTED, Application.REJECTED]),
                    )
                    created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} applications"))

    def seed_invitations(self, babysitters):
        """Seed invitations."""
        self.stdout.write("Seeding invitations...")

        if not babysitters:
            self.stdout.write(self.style.WARNING("  No babysitters found"))
            return

        unclaimed_tasks = list(Task.objects.filter(status=Task.UNCLAIMED))
        if not unclaimed_tasks:
            self.stdout.write(self.style.WARNING("  No unclaimed tasks"))
            return

        messages = [
            "Hi! I think you'd be perfect for this job.",
            "We've seen your profile and would love to have you!",
            "You came highly recommended.",
            None,
        ]

        created = 0
        for task in sample(unclaimed_tasks, min(len(unclaimed_tasks), len(unclaimed_tasks) // 3 + 1)):
            for babysitter in sample(babysitters, min(len(babysitters), randint(1, 2))):
                if not Invitation.objects.filter(task=task, babysitter=babysitter).exists():
                    status = choice([Invitation.PENDING] * 2 + [Invitation.ACCEPTED, Invitation.DECLINED])
                    Invitation.objects.create(
                        task=task,
                        babysitter=babysitter,
                        message=choice(messages),
                        status=status,
                        responded_at=timezone.now() if status != Invitation.PENDING else None,
                    )
                    created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} invitations"))

    def seed_availabilities(self, users):
        """Seed availability records."""
        self.stdout.write("Seeding availabilities...")

        if not users:
            self.stdout.write(self.style.WARNING("  No users found"))
            return

        now = timezone.now()
        created = 0

        for user in users:
            for _ in range(randint(2, 5)):
                avail_type = choice([UserAvailability.WEEKLY, UserAvailability.MONTHLY])
                if avail_type == UserAvailability.WEEKLY:
                    day_of_week = randint(0, 6)
                    days_ahead = (day_of_week - now.weekday()) % 7 or 7
                    date = None
                else:
                    day_of_week = None
                    days_ahead = randint(1, 30)
                    date = now + timedelta(days=days_ahead)

                start_time = now + timedelta(days=days_ahead, hours=randint(7, 18) - now.hour)
                end_time = start_time + timedelta(hours=randint(2, 6))

                UserAvailability.objects.create(
                    user=user,
                    type=avail_type,
                    day_of_week=day_of_week,
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                    whole_day=choice([True, False, False, False]),
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} availabilities"))

    def seed_reviews(self, parents, babysitters):
        """Seed reviews for claimed/completed tasks."""
        self.stdout.write("Seeding reviews...")

        tasks_with_volunteers = Task.objects.filter(
            status__in=[Task.CLAIMED, Task.COMPLETED],
            volunteer__isnull=False
        ).exclude(review__isnull=False)

        comments = [
            "Absolutely wonderful with the kids!",
            "Very professional and punctual.",
            "Great communication throughout.",
            "My children loved spending time with them.",
            "Experienced and patient.",
            "Trustworthy and reliable.",
            "Amazing with our toddler.",
            "Five stars! Arrived early, left the house spotless.",
        ]

        created = 0
        for task in tasks_with_volunteers:
            Review.objects.create(
                task=task,
                parent=task.user,
                volunteer=task.volunteer,
                rating=choice([4, 4, 5, 5, 5]),
                comment=choice(comments),
            )
            if hasattr(task.volunteer, 'babysitter_profile'):
                task.volunteer.babysitter_profile.update_rating()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} reviews"))

    def seed_notifications(self, users):
        """Seed notifications."""
        self.stdout.write("Seeding notifications...")

        if not users:
            self.stdout.write(self.style.WARNING("  No users found"))
            return

        tasks = list(Task.objects.all()[:20])
        templates = [
            (Notification.TASK_COMPLETED, "Task Completed", "Your babysitting task is complete."),
            (Notification.NEW_REVIEW, "New Review", "You've received a new 5-star review!"),
            (Notification.APPLICATION_ACCEPTED, "Application Accepted!", "Your application was accepted."),
            (Notification.APPLICATION_REJECTED, "Application Update", "Your application was not selected."),
            (Notification.NEW_APPLICATION, "New Application", "Someone applied for your task!"),
            (Notification.CUSTOM, "Welcome!", "Welcome to the platform!"),
        ]

        created = 0
        for user in users:
            for _ in range(randint(2, 5)):
                notif_type, title, message = choice(templates)
                related_task_id = choice(tasks).id if tasks else None
                Notification.objects.create(
                    user=user,
                    type=notif_type,
                    title=title,
                    message=message,
                    is_read=choice([True, False, False]),
                    related_task_id=related_task_id,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created} notifications"))
