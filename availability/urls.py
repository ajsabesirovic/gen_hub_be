from rest_framework.routers import DefaultRouter

from .views import UserAvailabilityViewSet

router = DefaultRouter()
router.register(r"availability", UserAvailabilityViewSet, basename="availability")

urlpatterns = router.urls
