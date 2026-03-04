from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import ParentProfile, User, BabysitterProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'name', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('User Information', {
            'fields': ('name', 'age', 'phone', 'city', 'country', 'role', 'profile_image')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('User Information', {
            'fields': ('name', 'age', 'phone', 'city', 'country', 'role', 'profile_image')
        }),
    )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_email', 'city', 'country', 'number_of_children')
    search_fields = ('user__email', 'user__name', 'city', 'country')
    list_filter = ('preferred_babysitting_location', 'pets_in_home', 'smoking_allowed')
    raw_id_fields = ('user',)
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Address', {'fields': ('street', 'apartment_number', 'city', 'country')}),
        ('Children', {'fields': ('number_of_children', 'children_ages')}),
        ('Preferences', {
            'fields': (
                'preferred_babysitting_location',
                'preferred_languages',
                'preferred_experience_years',
                'preferred_experience_with_ages',
                'smoking_allowed',
                'pets_in_home',
            )
        }),
        ('Special Needs', {'fields': ('has_special_needs', 'special_needs_description')}),
        ('Description', {'fields': ('description', 'additional_notes')}),
    )
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'


@admin.register(BabysitterProfile)
class BabysitterProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_email', 'experience_years', 'drivers_license', 'first_aid_certified')
    search_fields = ('user__email', 'user__name', 'languages', 'education')
    list_filter = ('preferred_babysitting_location', 'drivers_license', 'car', 'smoker', 'first_aid_certified')
    raw_id_fields = ('user',)
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('About', {'fields': ('description', 'experience_years', 'education', 'characteristics')}),
        ('Logistics', {'fields': ('drivers_license', 'car', 'has_children', 'smoker')}),
        ('Preferences', {'fields': ('preferred_babysitting_location', 'languages', 'experience_with_ages')}),
        ('Compliance', {'fields': ('background_check', 'first_aid_certified')}),
    )
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
