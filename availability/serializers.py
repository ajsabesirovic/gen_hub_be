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


class TimeRangeSerializer(serializers.Serializer):
    """Serializer for individual time ranges within a day."""
    id = serializers.CharField(required=False, allow_blank=True)
    from_time = serializers.CharField(source='from', required=False, allow_blank=True)
    to_time = serializers.CharField(source='to', required=False, allow_blank=True)

    def to_representation(self, instance):
        """Convert internal representation to frontend format."""
        return {
            'id': instance.get('id', ''),
            'from': instance.get('from', ''),
            'to': instance.get('to', ''),
        }

    def to_internal_value(self, data):
        """Convert frontend format to internal representation."""
        return {
            'id': data.get('id', ''),
            'from': data.get('from', ''),
            'to': data.get('to', ''),
        }


class WeeklyScheduleSerializer(serializers.Serializer):
    """Serializer for weekly schedule entries."""
    day = serializers.CharField()
    timeRanges = TimeRangeSerializer(many=True, required=False, default=list)
    whole_day = serializers.BooleanField(required=False, default=False)


class MonthlyScheduleSerializer(serializers.Serializer):
    """Serializer for monthly schedule entries."""
    date = serializers.CharField()
    from_time = serializers.CharField(source='from', required=False, allow_blank=True)
    to_time = serializers.CharField(source='to', required=False, allow_blank=True)
    whole_day = serializers.BooleanField(required=False, default=False)

    def to_representation(self, instance):
        """Convert internal representation to frontend format."""
        return {
            'date': instance.get('date', ''),
            'from': instance.get('from', ''),
            'to': instance.get('to', ''),
            'whole_day': instance.get('whole_day', False),
        }

    def to_internal_value(self, data):
        """Convert frontend format to internal representation."""
        return {
            'date': data.get('date', ''),
            'from': data.get('from', ''),
            'to': data.get('to', ''),
            'whole_day': data.get('whole_day', False),
        }


class AggregatedAvailabilitySerializer(serializers.Serializer):
    """
    Serializer for aggregated availability data.
    Matches the frontend AvailabilityData interface.
    """
    mode = serializers.ChoiceField(choices=['weekly', 'monthly'])
    weeklySchedule = WeeklyScheduleSerializer(many=True, required=False, default=list)
    monthlySchedule = MonthlyScheduleSerializer(many=True, required=False, default=list)
    currentMonth = serializers.CharField(required=False, allow_blank=True)
