from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import UserAvailabilityViewSet, AggregatedAvailabilityView

router = DefaultRouter()
router.register(r"availability", UserAvailabilityViewSet, basename="availability")

urlpatterns = [
    path('availability/aggregate/', AggregatedAvailabilityView.as_view(), name='availability-aggregate'),
] + router.urls
