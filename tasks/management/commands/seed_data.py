"""
Django management command to seed the database with demo data using existing users.

This script seeds all data EXCEPT users - it uses existing users in the database.

Usage:
    python manage.py seed_data
    python manage.py seed_data --flush
    python manage.py seed_data --tasks 20  # Create 20 tasks instead of default 10
"""

from datetime import timedelta
from random import choice, randint, sample

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.models import Application, Invitation
from availability.models import UserAvailability
from categories.models import Category
from notifications.models import Notification
from reviews.models import Review
from tasks.models import Task

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with demo data using existing users. Use --flush to remove seeded data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all seeded data (except users) instead of creating it",
        )
        parser.add_argument(
            "--tasks",
            type=int,
            default=10,
            help="Number of tasks to create (default: 10)",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.flush_data()
        else:
            self.seed_data(num_tasks=options["tasks"])

    def flush_data(self):
        """Delete all seeded data (except users)."""
        self.stdout.write(self.style.WARNING("Flushing seeded data (keeping users)..."))

        deleted_counts = {
            "reviews": Review.objects.all().delete()[0],
            "notifications": Notification.objects.all().delete()[0],
            "invitations": Invitation.objects.all().delete()[0],
            "applications": Application.objects.all().delete()[0],
            "tasks": Task.objects.all().delete()[0],
            "availabilities": UserAvailability.objects.all().delete()[0],
            "categories": Category.objects.all().delete()[0],
        }

        self.stdout.write(self.style.SUCCESS("\n✓ Flushed seeded data:"))
        for model_name, count in deleted_counts.items():
            self.stdout.write(f"  - {model_name}: {count} deleted")
        self.stdout.write(self.style.SUCCESS("\n✓ Users were NOT deleted."))

    def seed_data(self, num_tasks=10):
        """Create seed data for all models using existing users."""
        self.stdout.write(self.style.SUCCESS("Starting database seeding...\n"))

        babysitters, parents = self.get_existing_users()

        if not parents:
            self.stdout.write(
                self.style.ERROR("✗ No parent users found! Please create some users with role='parent' first.")
            )
            return

        if not babysitters:
            self.stdout.write(
                self.style.WARNING("⚠ No babysitter users found. Some features will be limited.")
            )

        categories = self.create_categories()
        tasks = self.create_tasks(babysitters, parents, categories, num_tasks)
        applications = self.create_applications(tasks, babysitters)
        invitations = self.create_invitations(tasks, babysitters)
        availabilities = self.create_availabilities(babysitters + parents)
        reviews = self.create_reviews(tasks, parents, babysitters)
        notifications = self.create_notifications(babysitters + parents, tasks)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("✓ Database seeding completed!"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"\nUsing existing users:")
        self.stdout.write(f"  - Parents: {len(parents)}")
        self.stdout.write(f"  - Babysitters: {len(babysitters)}")
        self.stdout.write(f"\nCreated:")
        self.stdout.write(f"  - Categories: {len(categories)}")
        self.stdout.write(f"  - Tasks: {len(tasks)}")
        self.stdout.write(f"  - Applications: {len(applications)}")
        self.stdout.write(f"  - Invitations: {len(invitations)}")
        self.stdout.write(f"  - Availabilities: {len(availabilities)}")
        self.stdout.write(f"  - Reviews: {len(reviews)}")
        self.stdout.write(f"  - Notifications: {len(notifications)}")

    def get_existing_users(self):
        """Get existing users from the database by role."""
        self.stdout.write("Fetching existing users...")

        babysitters = list(User.objects.filter(role="babysitter", is_active=True))
        parents = list(User.objects.filter(role="parent", is_active=True))

        self.stdout.write(f"  Found {len(parents)} parents")
        self.stdout.write(f"  Found {len(babysitters)} babysitters")

        return babysitters, parents

    def create_categories(self):
        """Create seed categories for babysitting tasks."""
        self.stdout.write("\nCreating categories...")

        category_data = [
            {
                "name": "Regular Babysitting",
                "description": "Standard babysitting for children of all ages",
            },
            {
                "name": "Newborn Care",
                "description": "Specialized care for infants and newborns",
            },
            {
                "name": "After School Care",
                "description": "Picking up children from school and supervising until parents return",
            },
            {
                "name": "Overnight Care",
                "description": "Babysitting that extends through the night",
            },
            {
                "name": "Weekend Care",
                "description": "Weekend babysitting services",
            },
            {
                "name": "Special Needs Care",
                "description": "Care for children with special needs or disabilities",
            },
            {
                "name": "Tutoring & Homework Help",
                "description": "Helping children with homework and educational activities",
            },
            {
                "name": "Pet Care (with children)",
                "description": "Taking care of children and family pets together",
            },
            {
                "name": "Event Babysitting",
                "description": "Babysitting for special events, parties, or occasions",
            },
            {
                "name": "Emergency Care",
                "description": "Last-minute or urgent babysitting needs",
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
            else:
                self.stdout.write(f"  - Category exists: {category.name}")

        return categories

    def create_tasks(self, babysitters, parents, categories, num_tasks=10):
        """Create seed tasks."""
        self.stdout.write("\nCreating tasks...")

        if not parents:
            self.stdout.write(self.style.WARNING("  ⚠ No parents found, skipping tasks"))
            return []

        task_templates = [
            {
                "title": "Evening Babysitter Needed",
                "description": "Looking for a reliable babysitter for our two kids (ages 4 and 7) on Friday evening. Kids are well-behaved and will need dinner and bedtime routine.",
                "duration": 240,
                "location": "123 Main Street",
            },
            {
                "title": "After School Pickup & Care",
                "description": "Need someone to pick up my daughter from school at 3pm and watch her until 6pm. She has homework to complete.",
                "duration": 180,
                "location": "Lincoln Elementary School",
            },
            {
                "title": "Weekend Date Night Sitter",
                "description": "Looking for a sitter for Saturday night. Two children ages 3 and 5. Pizza dinner and movie night planned.",
                "duration": 300,
                "location": "456 Oak Avenue",
            },
            {
                "title": "Infant Care - Daytime",
                "description": "Need experienced caregiver for our 6-month-old baby during work hours. Must be comfortable with feeding and nap schedules.",
                "duration": 480,
                "location": "789 Maple Drive",
            },
            {
                "title": "Overnight Babysitter",
                "description": "Looking for overnight care for one child (age 8) while we attend an out-of-town wedding. Saturday 6pm to Sunday 10am.",
                "duration": 960,
                "location": "321 Pine Street",
            },
            {
                "title": "Last Minute Sitter Needed",
                "description": "Emergency! Need a sitter ASAP for tomorrow. Three kids ages 6, 8, and 10. Will be mostly playing and watching movies.",
                "duration": 180,
                "location": "555 Elm Road",
            },
            {
                "title": "Homework Help & Tutoring",
                "description": "Looking for someone who can help my son (age 10) with math homework twice a week. Some babysitting involved.",
                "duration": 120,
                "location": "Home - 777 Cedar Lane",
            },
            {
                "title": "Newborn Night Nurse",
                "description": "First-time parents seeking experienced night care for our 2-week-old. Help with night feedings and soothing.",
                "duration": 480,
                "location": "888 Birch Boulevard",
            },
            {
                "title": "Summer Day Camp Supervision",
                "description": "Need a fun, energetic sitter for summer days. Two active boys (ages 5 and 7). Pool supervision required (certified lifeguard preferred).",
                "duration": 360,
                "location": "Home with pool",
            },
            {
                "title": "Special Needs Care",
                "description": "Experienced caregiver needed for my son with autism (age 9). Must be patient and familiar with sensory sensitivities.",
                "duration": 240,
                "location": "999 Willow Way",
            },
            {
                "title": "Party Helper Needed",
                "description": "Hosting a birthday party for my daughter. Need help supervising 10 kids (ages 5-7) for 3 hours. Games and cake!",
                "duration": 180,
                "location": "Community Center",
            },
            {
                "title": "Regular Weekly Sitter",
                "description": "Looking for consistent sitter for every Tuesday and Thursday evening. Two children, ages 4 and 6.",
                "duration": 240,
                "location": "Downtown apartment",
            },
            {
                "title": "Morning Nanny Needed",
                "description": "Need someone to help with morning routine - breakfast, getting dressed, and school drop-off for 3 kids.",
                "duration": 150,
                "location": "Suburban home",
            },
            {
                "title": "Pet-Friendly Babysitter",
                "description": "We have a friendly dog and two kids (ages 8 and 11). Need sitter comfortable with both kids and pets.",
                "duration": 180,
                "location": "Family home",
            },
            {
                "title": "Bilingual Caregiver Wanted",
                "description": "Seeking Spanish-speaking babysitter to help maintain our children's language skills. Ages 3 and 5.",
                "duration": 240,
                "location": "Near city center",
            },
        ]

        tasks = []
        now = timezone.now()

        for i in range(num_tasks):
            template = task_templates[i % len(task_templates)]
            parent = choice(parents)
            category = choice(categories)
            days_offset = randint(-14, 30)
            start_time = now + timedelta(days=days_offset, hours=randint(7, 19))
            end_time = start_time + timedelta(minutes=template["duration"])

            status_weights = [Task.UNCLAIMED] * 5 + [Task.CLAIMED] * 3 + [Task.COMPLETED] * 2
            status = choice(status_weights)

            volunteer = None
            if status in [Task.CLAIMED, Task.COMPLETED] and babysitters:
                volunteer = choice(babysitters)

            task = Task.objects.create(
                user=parent,
                volunteer=volunteer,
                category=category,
                title=template["title"],
                description=template["description"],
                start=start_time,
                end=end_time,
                whole_day=False,
                location=template["location"],
                status=status,
                duration=template["duration"],
                extra_dates={},
            )
            tasks.append(task)
            self.stdout.write(f"  ✓ Created task: {task.title[:40]}... ({task.status})")

        return tasks

    def create_applications(self, tasks, babysitters):
        """Create seed applications."""
        self.stdout.write("\nCreating applications...")

        if not tasks or not babysitters:
            self.stdout.write(
                self.style.WARNING("  ⚠ No tasks or babysitters found, skipping applications")
            )
            return []

        applications = []
        unclaimed_tasks = [t for t in tasks if t.status == Task.UNCLAIMED]

        for task in sample(unclaimed_tasks, min(len(unclaimed_tasks), max(1, len(unclaimed_tasks) // 2))):
            num_applications = randint(1, min(3, len(babysitters)))
            task_babysitters = sample(babysitters, num_applications)

            for babysitter in task_babysitters:
                if not Application.objects.filter(task=task, volunteer=babysitter).exists():
                    status = choice(
                        [Application.PENDING, Application.PENDING, Application.ACCEPTED, Application.REJECTED]
                    )
                    application = Application.objects.create(
                        task=task, volunteer=babysitter, status=status
                    )
                    applications.append(application)
                    self.stdout.write(
                        f"  ✓ Application: {babysitter.username} -> {task.title[:30]}... ({status})"
                    )

        return applications

    def create_invitations(self, tasks, babysitters):
        """Create seed invitations."""
        self.stdout.write("\nCreating invitations...")

        if not tasks or not babysitters:
            self.stdout.write(
                self.style.WARNING("  ⚠ No tasks or babysitters found, skipping invitations")
            )
            return []

        invitations = []
        unclaimed_tasks = [t for t in tasks if t.status == Task.UNCLAIMED]

        invitation_messages = [
            "Hi! I think you'd be perfect for this job. Would you be interested?",
            "We've seen your profile and would love to have you babysit for us!",
            "You came highly recommended. Please consider our request.",
            "Your experience with toddlers caught our attention. Would you be available?",
            None,
            None,
        ]

        for task in sample(unclaimed_tasks, min(len(unclaimed_tasks), max(1, len(unclaimed_tasks) // 3))):
            num_invitations = randint(1, min(2, len(babysitters)))
            task_babysitters = sample(babysitters, num_invitations)

            for babysitter in task_babysitters:
                if not Invitation.objects.filter(task=task, babysitter=babysitter).exists():
                    status = choice(
                        [Invitation.PENDING, Invitation.PENDING, Invitation.ACCEPTED, Invitation.DECLINED]
                    )
                    invitation = Invitation.objects.create(
                        task=task,
                        babysitter=babysitter,
                        message=choice(invitation_messages),
                        status=status,
                        responded_at=timezone.now() if status != Invitation.PENDING else None,
                    )
                    invitations.append(invitation)
                    self.stdout.write(
                        f"  ✓ Invitation: {task.user.username} -> {babysitter.username} ({status})"
                    )

        return invitations

    def create_availabilities(self, users):
        """Create seed availability records."""
        self.stdout.write("\nCreating availabilities...")

        if not users:
            self.stdout.write(self.style.WARNING("  ⚠ No users found, skipping availabilities"))
            return []

        availabilities = []
        days_of_week = list(range(7))

        for user in users:
            num_records = randint(2, 5)

            for _ in range(num_records):
                avail_type = choice([UserAvailability.WEEKLY, UserAvailability.MONTHLY])
                now = timezone.now()

                if avail_type == UserAvailability.WEEKLY:
                    day_of_week = choice(days_of_week)
                    days_ahead = (day_of_week - now.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    start_hour = randint(7, 18)
                    start_time = now + timedelta(days=days_ahead, hours=start_hour - now.hour)
                    end_time = start_time + timedelta(hours=randint(2, 6))
                    date = None
                else:
                    day_of_week = None
                    days_ahead = randint(1, 30)
                    start_hour = randint(7, 18)
                    start_time = now + timedelta(days=days_ahead, hours=start_hour - now.hour)
                    end_time = start_time + timedelta(hours=randint(2, 8))
                    date = start_time

                availability = UserAvailability.objects.create(
                    user=user,
                    type=avail_type,
                    day_of_week=day_of_week,
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                    whole_day=choice([True, False, False, False]),
                )
                availabilities.append(availability)

            self.stdout.write(f"  ✓ Created {num_records} availabilities for {user.username}")

        return availabilities

    def create_reviews(self, tasks, parents, babysitters):
        """Create seed reviews for completed tasks."""
        self.stdout.write("\nCreating reviews...")

        if not tasks or not parents or not babysitters:
            self.stdout.write(
                self.style.WARNING("  ⚠ Missing required data, skipping reviews")
            )
            return []

        reviews = []
        completed_or_claimed_tasks = [
            t for t in tasks
            if t.status in [Task.CLAIMED, Task.COMPLETED] and t.volunteer
        ]

        review_comments = [
            "Absolutely wonderful with the kids! They didn't want her to leave.",
            "Very professional and punctual. Kids were fed, bathed, and happy.",
            "Great communication throughout. Sent updates and photos.",
            "My children loved spending time with them. Highly recommend!",
            "Experienced and patient. Handled bedtime routine perfectly.",
            "Trustworthy and reliable. Will definitely book again.",
            "Amazing with our toddler. Knew exactly how to keep him entertained.",
            "Arrived early, left the house spotless. Five stars!",
            "Our go-to babysitter now. Kids ask for them by name.",
            "Very attentive and caring. Made us feel completely at ease.",
            "Followed all our instructions to the letter. Perfect!",
            "Creative with activities. Kids learned new games!",
        ]

        for task in completed_or_claimed_tasks:
            if not Review.objects.filter(task=task).exists():
                review = Review.objects.create(
                    task=task,
                    parent=task.user,
                    volunteer=task.volunteer,
                    rating=choice([4, 4, 5, 5, 5]),
                    comment=choice(review_comments),
                )
                reviews.append(review)

                if hasattr(task.volunteer, 'babysitter_profile'):
                    task.volunteer.babysitter_profile.update_rating()

                self.stdout.write(
                    f"  ✓ Review: {task.user.username} -> {task.volunteer.username} ({review.rating}★)"
                )

        return reviews

    def create_notifications(self, users, tasks):
        """Create seed notifications."""
        self.stdout.write("\nCreating notifications...")

        if not users:
            self.stdout.write(self.style.WARNING("  ⚠ No users found, skipping notifications"))
            return []

        notifications = []

        notification_templates = [
            {
                "type": Notification.TASK_COMPLETED,
                "title": "Task Completed",
                "message": "Your babysitting task has been marked as completed.",
            },
            {
                "type": Notification.NEW_REVIEW,
                "title": "New Review Received",
                "message": "You've received a new 5-star review! Check it out.",
            },
            {
                "type": Notification.APPLICATION_ACCEPTED,
                "title": "Application Accepted!",
                "message": "Great news! Your application has been accepted.",
            },
            {
                "type": Notification.APPLICATION_REJECTED,
                "title": "Application Update",
                "message": "Unfortunately, your application was not selected this time.",
            },
            {
                "type": Notification.NEW_APPLICATION,
                "title": "New Application",
                "message": "Someone has applied for your babysitting task!",
            },
            {
                "type": Notification.CUSTOM,
                "title": "Welcome!",
                "message": "Welcome to the platform! Complete your profile to get started.",
            },
            {
                "type": Notification.CUSTOM,
                "title": "Profile Reminder",
                "message": "Adding more details to your profile can help you get more jobs!",
            },
            {
                "type": Notification.CUSTOM,
                "title": "New Feature",
                "message": "Check out our new availability calendar feature!",
            },
        ]

        for user in users:
            num_notifications = randint(2, 5)
            user_notifications = sample(notification_templates, min(num_notifications, len(notification_templates)))

            for template in user_notifications:
                related_task_id = None
                if tasks and template["type"] in [
                    Notification.TASK_COMPLETED,
                    Notification.NEW_APPLICATION,
                    Notification.APPLICATION_ACCEPTED,
                ]:
                    related_task_id = choice(tasks).id

                notification = Notification.objects.create(
                    user=user,
                    type=template["type"],
                    title=template["title"],
                    message=template["message"],
                    is_read=choice([True, False, False]),
                    related_task_id=related_task_id,
                )
                notifications.append(notification)

            self.stdout.write(f"  ✓ Created {len(user_notifications)} notifications for {user.username}")

        return notifications
