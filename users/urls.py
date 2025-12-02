from rest_framework.routers import DefaultRouter
from .views import UserViewset

app_name = "users"

router = DefaultRouter()
router.register(prefix='',viewset=UserViewset,basename='users')

urlpatterns = router.urls