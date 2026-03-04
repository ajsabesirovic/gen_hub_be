from rest_framework import serializers
from .models import User, ParentProfile, BabysitterProfile


class AdminUserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users in admin panel - minimal fields"""
    profile_image = serializers.ImageField(use_url=True, read_only=True)
    profile_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'name',
            'role',
            'is_active',
            'is_staff',
            'is_superuser',
            'date_joined',
            'last_login',
            'profile_image',
            'city',
            'country',
            'profile_summary',
        )
        read_only_fields = (
            'id',
            'date_joined',
            'last_login',
            'is_staff',
            'is_superuser',
        )

    def get_profile_summary(self, obj):
        """Return a brief summary of the user's profile"""
        if obj.role == 'parent' and hasattr(obj, 'parent_profile'):
            profile = obj.parent_profile
            return {
                'number_of_children': profile.number_of_children,
                'city': profile.city or obj.city,
            }
        elif obj.role == 'babysitter' and hasattr(obj, 'babysitter_profile'):
            profile = obj.babysitter_profile
            return {
                'experience_years': profile.experience_years,
                'hourly_rate': float(profile.hourly_rate) if profile.hourly_rate else None,
                'first_aid_certified': profile.first_aid_certified,
            }
        return None


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for admin user management"""
    profile_image = serializers.ImageField(use_url=True, required=False, allow_null=True)
    parent_profile = serializers.SerializerMethodField()
    babysitter_profile = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'name',
            'first_name',
            'last_name',
            'age',
            'phone',
            'city',
            'country',
            'role',
            'is_active',
            'is_staff',
            'is_superuser',
            'date_joined',
            'last_login',
            'profile_image',
            'parent_profile',
            'babysitter_profile',
            'task_count',
            'application_count',
        )
        read_only_fields = (
            'id',
            'date_joined',
            'last_login',
            'is_staff',
            'is_superuser',
        )

    def get_parent_profile(self, obj):
        if obj.role == 'parent' and hasattr(obj, 'parent_profile'):
            profile = obj.parent_profile
            return {
                'id': str(profile.id),
                'street': profile.street,
                'apartment_number': profile.apartment_number,
                'city': profile.city,
                'country': profile.country,
                'number_of_children': profile.number_of_children,
                'children_ages': profile.children_ages,
                'has_special_needs': profile.has_special_needs,
                'description': profile.description,
            }
        return None

    def get_babysitter_profile(self, obj):
        if obj.role == 'babysitter' and hasattr(obj, 'babysitter_profile'):
            profile = obj.babysitter_profile
            return {
                'id': str(profile.id),
                'experience_years': profile.experience_years,
                'hourly_rate': float(profile.hourly_rate) if profile.hourly_rate else None,
                'education': profile.education,
                'languages': profile.languages,
                'background_check': profile.background_check,
                'first_aid_certified': profile.first_aid_certified,
                'description': profile.description,
            }
        return None

    def get_task_count(self, obj):
        if obj.role == 'parent':
            return obj.created_tasks.count()
        elif obj.role == 'babysitter':
            return obj.assigned_tasks.count()
        return 0

    def get_application_count(self, obj):
        if obj.role == 'babysitter':
            return obj.task_applications.count()
        return 0

    def validate_role(self, value):
        """Allow admins to change user roles"""
        if value not in ['parent', 'babysitter', None]:
            raise serializers.ValidationError("Invalid role. Must be 'parent', 'babysitter', or null.")
        return value

    def validate(self, attrs):
        """Prevent changing admin users to regular roles"""
        instance = self.instance
        if instance:
            if instance.is_staff or instance.is_superuser:
                if 'role' in attrs and attrs.get('role') is not None:
                    raise serializers.ValidationError(
                        "Cannot set role for admin users. Remove admin privileges first."
                    )
        return attrs

    def update(self, instance, validated_data):
        """Update user with proper handling"""
        validated_data.pop('is_staff', None)
        validated_data.pop('is_superuser', None)
        
        return super().update(instance, validated_data)

