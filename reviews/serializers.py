from rest_framework import serializers

from tasks.models import Task
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), source="task", write_only=True, required=False
    )
    task = serializers.StringRelatedField(read_only=True)
    senior = serializers.StringRelatedField(read_only=True)
    volunteer = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "task",
            "task_id",
            "senior",
            "volunteer",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["created_at"]
