from rest_framework import serializers

from tasks.models import Task
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), source="task", write_only=True, required=False
    )
    task_uuid = serializers.UUIDField(source="task.id", read_only=True)
    task = serializers.StringRelatedField(read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True)
    parent = serializers.StringRelatedField(read_only=True)
    parent_id = serializers.UUIDField(source="parent.id", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    parent_profile_image = serializers.SerializerMethodField()
    volunteer = serializers.StringRelatedField(read_only=True)
    volunteer_id = serializers.UUIDField(source="volunteer.id", read_only=True)
    volunteer_name = serializers.CharField(source="volunteer.name", read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "task",
            "task_id",
            "task_uuid",
            "task_title",
            "parent",
            "parent_id",
            "parent_name",
            "parent_profile_image",
            "volunteer",
            "volunteer_id",
            "volunteer_name",
            "rating",
            "comment",
            "created_at",
            "updated_at",
            "is_editable",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_is_editable(self, obj):
        return obj.is_editable()

    def get_parent_profile_image(self, obj):
        if obj.parent and obj.parent.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.parent.profile_image.url)
            return obj.parent.profile_image.url
        return None
