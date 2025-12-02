from rest_framework import serializers

from tasks.models import Task
from tasks.serializers import TaskSerializer
from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), source="task", write_only=True, required=False
    )
    volunteer = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Application
        fields = ["id", "task", "task_id", "volunteer", "status", "created_at"]
        read_only_fields = ["status", "created_at"]
