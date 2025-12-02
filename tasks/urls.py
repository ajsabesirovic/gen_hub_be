from rest_framework.routers import DefaultRouter

from .views import StatisticsViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"statistics", StatisticsViewSet, basename="statistics")

urlpatterns = router.urls
