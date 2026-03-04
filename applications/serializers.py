from rest_framework import serializers

from tasks.models import Task
from tasks.serializers import TaskSerializer
from users.serializers import PublicBabysitterSerializer
from .models import Application, Invitation


class ApplicationSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), source="task", write_only=True, required=False
    )
    volunteer = serializers.StringRelatedField(read_only=True)
    volunteer_detail = PublicBabysitterSerializer(source="volunteer", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "task", "task_id", "volunteer", "volunteer_detail", "status", "created_at"]
        read_only_fields = ["status", "created_at"]


class InvitationSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), source="task", write_only=True, required=False
    )
    babysitter = serializers.StringRelatedField(read_only=True)
    babysitter_detail = PublicBabysitterSerializer(source="babysitter", read_only=True)
    parent_detail = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ["id", "task", "task_id", "babysitter", "babysitter_detail", "parent_detail", "message", "status", "created_at", "responded_at"]
        read_only_fields = ["status", "created_at", "responded_at"]

    def get_parent_detail(self, obj):
        """Return the parent (task owner) details."""
        parent = obj.task.user
        return {
            "id": str(parent.id),
            "name": parent.name or parent.email.split("@")[0],
            "email": parent.email,
            "profile_image": parent.profile_image.url if parent.profile_image else None,
        }
