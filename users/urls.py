from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ParentProfileView, UserViewset, BabysitterProfileView, AdminUserViewSet

app_name = "users"

router = DefaultRouter()
router.register(prefix='', viewset=UserViewset, basename='users')
router.register(prefix='admin/users', viewset=AdminUserViewSet, basename='admin-users')

urlpatterns = [
    path('profile/parent/', ParentProfileView.as_view(), name='parent-profile'),
    path('profile/babysitter/', BabysitterProfileView.as_view(), name='babysitter-profile'),
] + router.urls

