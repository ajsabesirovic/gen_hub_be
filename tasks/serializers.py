from rest_framework import serializers

from categories.models import Category
from categories.serializers import CategorySerializer
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source="category",
        write_only=True,
    )
    end = serializers.DateTimeField(required=False, allow_null=True)
    duration = serializers.IntegerField(required=False, allow_null=True)
    user = serializers.StringRelatedField(read_only=True)

    # Geocoding fields - can be provided by frontend or set by backend
    formatted_address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)

    applications_count = serializers.SerializerMethodField()
    pending_applications_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "start",
            "end",
            "whole_day",
            "category",
            "category_id",
            "location",
            "formatted_address",
            "latitude",
            "longitude",
            "status",
            "duration",
            "extra_dates",
            "created_at",
            "updated_at",
            "volunteer",
            "user",
            "applications_count",
            "pending_applications_count",
        ]
        read_only_fields = ["status", "created_at", "updated_at", "volunteer", "user"]

    def get_applications_count(self, obj):
        """Return total number of applications for this task."""
        return obj.applications.count()

    def get_pending_applications_count(self, obj):
        """Return number of pending applications for this task."""
        return obj.applications.filter(status='pending').count()

    def validate(self, attrs):
        start = attrs.get("start", getattr(self.instance, "start", None))
        end = attrs.get("end", getattr(self.instance, "end", None))
        if start and end and start >= end:
            raise serializers.ValidationError("End time must be after start time.")
        duration = attrs.get("duration", getattr(self.instance, "duration", None))
        if duration is not None and duration <= 0:
            raise serializers.ValidationError({"duration": "Duration must be positive."})
        return attrs


class TaskDetailSerializer(TaskSerializer):
    volunteer = serializers.StringRelatedField(read_only=True)

    class Meta(TaskSerializer.Meta):
        pass
