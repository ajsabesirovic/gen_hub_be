"""
Serializers for statistics endpoints.

These serializers are read-only and used for API response documentation.
Statistics are computed on-the-fly, not from database models.
"""

from rest_framework import serializers


class MostHiredBabysitterSerializer(serializers.Serializer):
    """Serializer for most hired babysitter data."""
    id = serializers.CharField()
    name = serializers.CharField()
    hire_count = serializers.IntegerField()


class ParentStatisticsSerializer(serializers.Serializer):
    """
    Serializer for parent statistics.
    All fields are read-only computed values.
    """
    total_bookings = serializers.IntegerField(help_text="Total tasks/bookings created")
    completed_bookings = serializers.IntegerField(help_text="Bookings that were completed")
    cancelled_bookings = serializers.IntegerField(help_text="Bookings that were cancelled/unfilled")
    upcoming_bookings = serializers.IntegerField(help_text="Future bookings")
    total_hours = serializers.FloatField(help_text="Total babysitting hours")
    average_duration_minutes = serializers.IntegerField(help_text="Average booking duration in minutes")
    most_hired_babysitter = MostHiredBabysitterSerializer(
        allow_null=True,
        help_text="Most frequently hired babysitter"
    )
    total_spent = serializers.FloatField(help_text="Total amount spent (based on babysitter rates)")


class EarningsPerMonthSerializer(serializers.Serializer):
    """Serializer for monthly earnings data."""
    month = serializers.CharField(allow_null=True)
    earnings = serializers.FloatField()
    hours = serializers.FloatField()


class BabysitterStatisticsSerializer(serializers.Serializer):
    """
    Serializer for babysitter statistics.
    All fields are read-only computed values.
    """
    total_jobs = serializers.IntegerField(help_text="Total jobs accepted/assigned")
    completed_jobs = serializers.IntegerField(help_text="Jobs completed")
    cancelled_jobs = serializers.IntegerField(help_text="Applications that were rejected")
    total_hours = serializers.FloatField(help_text="Total hours worked")
    average_duration_minutes = serializers.IntegerField(help_text="Average job duration in minutes")
    total_earnings = serializers.FloatField(help_text="Total earnings based on hourly rate")
    hourly_rate = serializers.FloatField(help_text="Current hourly rate from profile")
    average_rating = serializers.FloatField(help_text="Average rating from reviews")
    review_count = serializers.IntegerField(help_text="Number of reviews received")
    repeat_parents = serializers.IntegerField(help_text="Number of parents who hired more than once")
    earnings_per_month = EarningsPerMonthSerializer(many=True, help_text="Monthly earnings breakdown")


class UserTotalsSerializer(serializers.Serializer):
    """Serializer for user count breakdown."""
    total = serializers.IntegerField()
    parents = serializers.IntegerField()
    babysitters = serializers.IntegerField()
    admins = serializers.IntegerField()
    active_parents = serializers.IntegerField()
    active_babysitters = serializers.IntegerField()


class NewUsersPerMonthSerializer(serializers.Serializer):
    """Serializer for new users per month."""
    month = serializers.CharField(allow_null=True)
    count = serializers.IntegerField()


class BookingsPerMonthSerializer(serializers.Serializer):
    """Serializer for bookings per month."""
    month = serializers.CharField(allow_null=True)
    count = serializers.IntegerField()


class TasksByStatusSerializer(serializers.Serializer):
    """Serializer for tasks by status."""
    unclaimed = serializers.IntegerField()
    claimed = serializers.IntegerField()
    total = serializers.IntegerField()


class ApplicationsByStatusSerializer(serializers.Serializer):
    """Serializer for applications by status."""
    pending = serializers.IntegerField()
    accepted = serializers.IntegerField()
    rejected = serializers.IntegerField()
    total = serializers.IntegerField()


class TasksPerCategorySerializer(serializers.Serializer):
    """Serializer for tasks per category."""
    category = serializers.CharField()
    count = serializers.IntegerField()


class TasksPerDaySerializer(serializers.Serializer):
    """Serializer for tasks per day chart data."""
    date = serializers.CharField(allow_null=True)
    count = serializers.IntegerField()


class BusiestDaysSerializer(serializers.Serializer):
    """Serializer for busiest days of week chart data."""
    day = serializers.CharField()
    count = serializers.IntegerField()


class StatusDistributionSerializer(serializers.Serializer):
    """Serializer for application status distribution."""
    status = serializers.CharField()
    count = serializers.IntegerField()


class CategoryDistributionSerializer(serializers.Serializer):
    """Serializer for category distribution."""
    category = serializers.CharField()
    count = serializers.IntegerField()


class LocationDistributionSerializer(serializers.Serializer):
    """Serializer for location distribution."""
    location = serializers.CharField()
    count = serializers.IntegerField()


class BabysitterDashboardStatisticsSerializer(serializers.Serializer):
    """
    Serializer for babysitter dashboard statistics.
    All fields are read-only computed values.
    """
    total_applications = serializers.IntegerField(help_text="Total applications submitted in the time range")
    accepted_applications = serializers.IntegerField(help_text="Number of accepted applications")
    cancelled_applications = serializers.IntegerField(help_text="Number of cancelled applications")
    completed_tasks = serializers.IntegerField(help_text="Number of completed tasks")
    acceptance_rate = serializers.FloatField(help_text="Percentage of accepted applications")
    cancellation_rate = serializers.FloatField(help_text="Percentage of cancelled applications")
    tasks_per_day = TasksPerDaySerializer(many=True, help_text="Tasks per day for line chart")
    busiest_days = BusiestDaysSerializer(many=True, help_text="Busiest days of week for bar chart")
    status_distribution = StatusDistributionSerializer(many=True, help_text="Application status distribution for pie chart")
    category_distribution = CategoryDistributionSerializer(many=True, help_text="Task category distribution for pie chart")
    location_distribution = LocationDistributionSerializer(many=True, help_text="Work location distribution for pie chart")
    total_unique_parents = serializers.IntegerField(help_text="Total number of unique parents worked with")
    repeat_parents_count = serializers.IntegerField(help_text="Number of parents who hired more than once")
    repeat_rate = serializers.FloatField(help_text="Percentage of repeat clients")
    total_hours_worked = serializers.FloatField(help_text="Total hours worked in the time range")
    average_task_duration = serializers.IntegerField(help_text="Average task duration in minutes")
    average_rating = serializers.FloatField(help_text="Average rating from reviews")
    review_count = serializers.IntegerField(help_text="Number of reviews received")
    range_days = serializers.IntegerField(help_text="Number of days in the filter range")


class TopBabysitterSerializer(serializers.Serializer):
    """Serializer for top babysitter data."""
    id = serializers.CharField()
    name = serializers.CharField()
    task_count = serializers.IntegerField()


class ParentDashboardStatisticsSerializer(serializers.Serializer):
    """
    Serializer for parent dashboard statistics.
    All fields are read-only computed values.
    """
    total_posted_tasks = serializers.IntegerField(help_text="Total tasks posted in the time range")
    accepted_tasks = serializers.IntegerField(help_text="Number of accepted/claimed tasks")
    cancelled_tasks = serializers.IntegerField(help_text="Number of cancelled tasks")
    completed_tasks = serializers.IntegerField(help_text="Number of completed tasks")
    acceptance_rate = serializers.FloatField(help_text="Percentage of accepted tasks")
    cancellation_rate = serializers.FloatField(help_text="Percentage of cancelled tasks")
    tasks_posted_per_day = TasksPerDaySerializer(many=True, help_text="Tasks posted per day for line chart")
    tasks_completed_per_day = TasksPerDaySerializer(many=True, help_text="Tasks completed per day for line chart")
    busiest_days = BusiestDaysSerializer(many=True, help_text="Busiest days of week for bar chart")
    status_distribution = StatusDistributionSerializer(many=True, help_text="Task status distribution for pie chart")
    category_distribution = CategoryDistributionSerializer(many=True, help_text="Task category distribution for pie chart")
    location_distribution = LocationDistributionSerializer(many=True, help_text="Task location distribution for pie chart")
    total_unique_babysitters = serializers.IntegerField(help_text="Total unique babysitters hired")
    repeat_babysitters_count = serializers.IntegerField(help_text="Number of babysitters hired more than once")
    repeat_rate = serializers.FloatField(help_text="Percentage of repeat babysitters")
    top_babysitters = TopBabysitterSerializer(many=True, help_text="Top 5 babysitters by task count")
    avg_time_to_first_application_hours = serializers.FloatField(help_text="Average hours until first application")
    avg_time_to_acceptance_hours = serializers.FloatField(help_text="Average hours until task acceptance")
    tasks_without_applications_percent = serializers.FloatField(help_text="Percentage of tasks without applications")
    total_hours_booked = serializers.FloatField(help_text="Total hours booked in the time range")
    average_task_duration = serializers.IntegerField(help_text="Average task duration in minutes")
    total_spent = serializers.FloatField(help_text="Total amount spent")
    average_cost_per_task = serializers.FloatField(help_text="Average cost per task")
    average_rating = serializers.FloatField(help_text="Average rating given by parent")
    review_count = serializers.IntegerField(help_text="Number of reviews given")
    range_days = serializers.IntegerField(help_text="Number of days in the filter range")


class AdminStatisticsSerializer(serializers.Serializer):
    """
    Serializer for admin/global statistics.
    All fields are read-only computed values.
    """
    user_totals = UserTotalsSerializer(help_text="User count breakdown by role")
    new_users_per_month = NewUsersPerMonthSerializer(many=True, help_text="New user registrations per month")
    total_bookings = serializers.IntegerField(help_text="Total bookings/tasks on platform")
    bookings_per_month = BookingsPerMonthSerializer(many=True, help_text="Bookings created per month")
    tasks_by_status = TasksByStatusSerializer(help_text="Task count by status")
    completion_rate = serializers.FloatField(help_text="Percentage of completed bookings")
    cancellation_rate = serializers.FloatField(help_text="Percentage of cancelled/unfilled bookings")
    average_duration_minutes = serializers.FloatField(help_text="Average booking duration in minutes")
    parent_to_babysitter_ratio = serializers.FloatField(help_text="Ratio of parents to babysitters")
    applications_by_status = ApplicationsByStatusSerializer(help_text="Application count by status")
    average_rating = serializers.FloatField(help_text="Platform-wide average babysitter rating")
    total_reviews = serializers.IntegerField(help_text="Total number of reviews")
    tasks_per_category = TasksPerCategorySerializer(many=True, help_text="Task distribution by category")
