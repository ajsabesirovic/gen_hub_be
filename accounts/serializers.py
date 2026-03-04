import re
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer


class CustomRegisterSerializer(RegisterSerializer):
    """
    Extend the default dj-rest-auth serializer so we can capture optional profile
    metadata at signup while keeping the base validation intact.
    """

    name = serializers.CharField(required=False, allow_blank=True)

    def validate_password1(self, password):
        """
        Validate password meets requirements:
        - At least 6 characters
        - At least one uppercase letter
        - At least one number
        - At least one special character
        """
        errors = []
        
        if len(password) < 6:
            errors.append("This password must contain at least 6 characters.")
        
        if not re.search(r'[A-Z]', password):
            errors.append("This password must contain at least one uppercase letter.")
        
        if not re.search(r'[0-9]', password):
            errors.append("This password must contain at least one number.")
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
            errors.append("This password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return password


    def get_cleaned_data(self):
        cleaned_data = super().get_cleaned_data()
        cleaned_data['name'] = self.validated_data.get('name', '')
        return cleaned_data

    def custom_signup(self, request, user):
        name = self.validated_data.get('name')

        if name is not None:
            user.name = name.strip()
        if name is not None:
            user.save()

        return user
    
