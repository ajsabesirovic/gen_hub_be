"""
URL configuration for statistics endpoints.

Routes:
- GET /api/stats/parent/ - Parent statistics
- GET /api/stats/parent/dashboard/ - Parent dashboard with time filtering
- GET /api/stats/babysitter/ - Babysitter statistics
- GET /api/stats/babysitter/dashboard/ - Babysitter dashboard with time filtering
- GET /api/stats/admin/ - Admin/global statistics
"""

from django.urls import path

from .views import (
    AdminStatisticsView,
    BabysitterDashboardView,
    BabysitterStatisticsView,
    ParentDashboardView,
    ParentStatisticsView,
)

urlpatterns = [
    path('parent/', ParentStatisticsView.as_view(), name='stats-parent'),
    path('parent/dashboard/', ParentDashboardView.as_view(), name='stats-parent-dashboard'),
    path('babysitter/', BabysitterStatisticsView.as_view(), name='stats-babysitter'),
    path('babysitter/dashboard/', BabysitterDashboardView.as_view(), name='stats-babysitter-dashboard'),
    path('admin/', AdminStatisticsView.as_view(), name='stats-admin'),
]
