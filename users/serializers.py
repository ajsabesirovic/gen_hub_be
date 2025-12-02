from django.contrib.auth import authenticate
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'name', 'age', 'phone',
            'first_name',
            'street', 'house_number', 'city', 'country', 'skills', 'role',
        )
        read_only_fields = ('id', 'date_joined', 'last_login', 'is_active', 'is_staff','username','email')

    def validate_role(self, value):
        if self.instance and self.instance.role is not None:
            raise serializers.ValidationError("Role cannot be changed once set.")
        return value

    def update(self, instance, validated_data):
        if instance.role is not None and 'role' in validated_data:
            validated_data.pop('role', None)
        
        return super().update(instance, validated_data)


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

