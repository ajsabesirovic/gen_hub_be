from django.contrib.auth import authenticate
from rest_framework import serializers
from dj_rest_auth.serializers import LoginSerializer
from .models import User, ParentProfile, BabysitterProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'name',
            'age',
            'phone',
            'first_name',
            'last_name',
            'city',
            'country',
            'role',
            'is_staff',
            'is_superuser',
        )
        read_only_fields = (
            'id',
            'is_staff',
            'is_superuser',
            'username',
            'email',
        )

    def validate_role(self, value):
        if self.instance and self.instance.role is not None and value != self.instance.role:
            raise serializers.ValidationError("Role cannot be changed once set.")
        return value

    
class CustomLoginSerializer(LoginSerializer):
    """
    Custom login serializer that allows users to login with either username or email
    in the 'username' field. If the value contains '@', authenticate using email,
    otherwise authenticate using username.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'email' in self.fields:
            del self.fields['email']
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            if '@' in username:
                try:
                    user = User.objects.get(email__iexact=username)
                    user = authenticate(
                        request=self.context.get('request'),
                        username=user.username,
                        password=password,
                    )
                except User.DoesNotExist:
                    user = None
            else:
                user = authenticate(
                    request=self.context.get('request'),
                    username=username,
                    password=password,
                )
            
            if not user:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg)
            
            if not user.is_active:
                msg = 'User account is disabled.'
                raise serializers.ValidationError(msg)
            
            attrs['user'] = user
            return attrs
        else:
            msg = 'Must include "username" and "password".'
            raise serializers.ValidationError(msg)


class ParentProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = ParentProfile
        fields = (
            'id',
            'user',
            'user_email',
            'user_name',
            'street',
            'apartment_number',
            'city',
            'country',
            'formatted_address',
            'latitude',
            'longitude',
            'number_of_children',
            'children_ages',
            'has_special_needs',
            'special_needs_description',
            'description',
            'preferred_babysitting_location',
            'preferred_languages',
            'preferred_experience_years',
            'preferred_experience_with_ages',
            'smoking_allowed',
            'pets_in_home',
            'additional_notes',
        )
        read_only_fields = ('id', 'user')
    
    def validate(self, attrs):
        if self.instance:
            user = self.instance.user
            if user.role != 'parent':
                raise serializers.ValidationError(
                    "Profile can only be updated for users with parent role."
                )
            if user.is_staff or user.is_superuser:
                raise serializers.ValidationError(
                    "Admin users cannot have profiles."
                )
        return attrs


class BabysitterProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = BabysitterProfile
        fields = (
            'id',
            'user',
            'user_email',
            'user_name',
            'description',
            'experience_years',
            'hourly_rate',
            'education',
            'characteristics',
            'drivers_license',
            'car',
            'has_children',
            'smoker',
            'street',
            'apartment_number',
            'formatted_address',
            'latitude',
            'longitude',
            'preferred_babysitting_location',
            'languages',
            'experience_with_ages',
            'background_check',
            'first_aid_certified',
            'average_rating',
            'total_reviews',
        )
        read_only_fields = ('id', 'user', 'background_check', 'first_aid_certified', 'average_rating', 'total_reviews')
    
    def validate(self, attrs):
        if self.instance:
            user = self.instance.user
            if user.role != 'babysitter':
                raise serializers.ValidationError(
                    "Profile can only be updated for users with babysitter role."
                )
            if user.is_staff or user.is_superuser:
                raise serializers.ValidationError(
                    "Admin users cannot have profiles."
                )
        return attrs


class UserWithProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for auth/user/ that returns user info plus their role-specific profile.
    """

    profile_image = serializers.ImageField(
        allow_null=True,
        required=False,
        use_url=True,
    )
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'name',
            'age',
            'phone',
            'first_name',
            'last_name',
            'city',
            'country',
            'role',
            'is_staff',
            'is_superuser',
            'profile_image',
            'profile',
        )
        read_only_fields = (
            'id',
            'email',
            'is_staff',
            'is_superuser',
        )

    def validate_role(self, value):
        """
        Prevent changing role once it has been set.

        Role may be provided only when the user has no role yet.
        """
        instance = getattr(self, "instance", None)
        if instance and instance.role is not None and value != instance.role:
            raise serializers.ValidationError("Role cannot be changed once set.")
        return value

    def validate_username(self, value):
        instance = getattr(self, "instance", None)
        if instance and value == instance.username:
            return value

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")

        return value

    def validate_profile_image(self, value):
        """
        Allow explicit null to remove image. DRF will handle file validation.
        """
        return value

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        return user

    def get_profile(self, obj):
        profile_map = {
            "babysitter": ("babysitter_profile", BabysitterProfileSerializer),
            "parent": ("parent_profile", ParentProfileSerializer),
        }

        if obj.role not in profile_map:
            return None

        related_name, serializer_class = profile_map[obj.role]

        profile = getattr(obj, related_name, None)
        if not profile:
            return None

        return serializer_class(profile).data


class PublicBabysitterProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabysitterProfile
        fields = (
            "description",
            "experience_years",
            "hourly_rate",
            "education",
            "characteristics",
            "drivers_license",
            "car",
            "has_children",
            "smoker",
            "preferred_babysitting_location",
            "languages",
            "experience_with_ages",
            "background_check",
            "first_aid_certified",
            "average_rating",
            "total_reviews",
        )


class PublicBabysitterSerializer(serializers.ModelSerializer):
    profile = PublicBabysitterProfileSerializer(source="babysitter_profile", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "name",
            "age",
            "city",
            "country",
            "profile_image",
            "role",
            "profile",
        )


class MeUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "name",
            "age",
            "phone",
            "city",
            "country",
            "profile_image",
            "role",
        )
        read_only_fields = ("id", "role")


class MeParentProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentProfile
        fields = (
            "street",
            "apartment_number",
            "city",
            "country",
            "formatted_address",
            "latitude",
            "longitude",
            "number_of_children",
            "children_ages",
            "has_special_needs",
            "special_needs_description",
            "description",
            "preferred_babysitting_location",
            "preferred_languages",
            "preferred_experience_years",
            "preferred_experience_with_ages",
            "smoking_allowed",
            "pets_in_home",
            "additional_notes",
        )


class MeBabysitterProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabysitterProfile
        fields = (
            "description",
            "experience_years",
            "hourly_rate",
            "education",
            "characteristics",
            "drivers_license",
            "car",
            "has_children",
            "smoker",
            "street",
            "apartment_number",
            "formatted_address",
            "latitude",
            "longitude",
            "preferred_babysitting_location",
            "languages",
            "experience_with_ages",
            "background_check",
            "first_aid_certified",
            "average_rating",
            "total_reviews",
        )
        read_only_fields = ("background_check", "first_aid_certified", "average_rating", "total_reviews")


class MeProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    age = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    profile_image = serializers.ImageField(
        allow_null=True,
        required=False,
        use_url=True,
    )
    role = serializers.CharField(read_only=True)

    street = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    apartment_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    formatted_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    number_of_children = serializers.IntegerField(required=False, allow_null=True)
    children_ages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    has_special_needs = serializers.BooleanField(required=False)
    special_needs_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    preferred_babysitting_location = serializers.ChoiceField(
        choices=["parents_home", "babysitters_home", "flexible"],
        required=False,
        allow_null=True,
    )
    preferred_languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    preferred_experience_years = serializers.IntegerField(required=False, allow_null=True)
    preferred_experience_with_ages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    smoking_allowed = serializers.BooleanField(required=False)
    pets_in_home = serializers.BooleanField(required=False)
    additional_notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    experience_years = serializers.IntegerField(required=False, allow_null=True)
    hourly_rate = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    education = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    characteristics = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    drivers_license = serializers.BooleanField(required=False)
    car = serializers.BooleanField(required=False)
    has_children = serializers.BooleanField(required=False)
    smoker = serializers.BooleanField(required=False)
    languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    experience_with_ages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    background_check = serializers.BooleanField(required=False)
    first_aid_certified = serializers.BooleanField(required=False)

    def to_representation(self, instance):
        user = instance
        user_data = MeUserUpdateSerializer(user, context=self.context).data
        data = dict(user_data)

        if user.role == "parent" and hasattr(user, "parent_profile"):
            profile_data = MeParentProfileUpdateSerializer(
                user.parent_profile, context=self.context
            ).data
            data.update(profile_data)
        elif user.role == "babysitter" and hasattr(user, "babysitter_profile"):
            profile_data = MeBabysitterProfileUpdateSerializer(
                user.babysitter_profile, context=self.context
            ).data
            data.update(profile_data)

        return data

    def update(self, instance, validated_data):
        user = instance
        user_fields = {
            field: validated_data[field]
            for field in (
                "name",
                "age",
                "phone",
                "city",
                "country",
                "profile_image",
            )
            if field in validated_data
        }

        if user.role == "parent":
            profile = getattr(user, "parent_profile", None)
            if profile is None:
                profile = ParentProfile.objects.create(user=user)
            profile_serializer_class = MeParentProfileUpdateSerializer
            profile_field_names = profile_serializer_class.Meta.fields
        elif user.role == "babysitter":
            profile = getattr(user, "babysitter_profile", None)
            if profile is None:
                profile = BabysitterProfile.objects.create(user=user)
            profile_serializer_class = MeBabysitterProfileUpdateSerializer
            profile_field_names = profile_serializer_class.Meta.fields
        else:
            profile = None
            profile_serializer_class = None
            profile_field_names = []

        profile_fields = {
            field: validated_data[field]
            for field in profile_field_names
            if field in validated_data
        }

        if user_fields:
            user_serializer = MeUserUpdateSerializer(
                user, data=user_fields, partial=True, context=self.context
            )
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()

        if profile and profile_fields:
            profile_serializer = profile_serializer_class(
                profile, data=profile_fields, partial=True, context=self.context
            )
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()

        return user
