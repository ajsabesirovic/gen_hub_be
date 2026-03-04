from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "is_read",
            "created_at",
            "related_task_id",
            "related_user_id",
        ]
        read_only_fields = ["created_at"]
