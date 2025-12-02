from rest_framework import serializers

from .models import UserAvailability


class UserAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAvailability
        fields = [
            "id",
            "type",
            "day_of_week",
            "date",
            "start_time",
            "end_time",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        availability_type = attrs.get("type", getattr(self.instance, "type", None))
        day = attrs.get("day_of_week", getattr(self.instance, "day_of_week", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))

        if availability_type == UserAvailability.WEEKLY and day is None:
            raise serializers.ValidationError({"day_of_week": "Weekly availability requires day_of_week."})
        if availability_type == UserAvailability.MONTHLY and date is None:
            raise serializers.ValidationError({"date": "Monthly availability requires a date."})
        if start and end and start >= end:
            raise serializers.ValidationError("End time must be after start time.")
        return attrs
