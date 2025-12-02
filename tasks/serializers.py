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

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "start",
            "end",
            "whole_day",
            "color",
            "category",
            "category_id",
            "location",
            "status",
            "duration",
            "extra_dates",
            "created_at",
            "updated_at",
            "volunteer",
        ]
        read_only_fields = ["status", "created_at", "updated_at", "volunteer"]

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
    user = serializers.StringRelatedField(read_only=True)

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["user"]
