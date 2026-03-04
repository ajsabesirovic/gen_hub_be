"""
Statistics views for the babysitting marketplace.

Provides read-only endpoints for:
- GET /api/stats/parent/ - Parent's own statistics
- GET /api/stats/babysitter/ - Babysitter's own statistics
- GET /api/stats/admin/ - Global platform statistics (admin only)
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gen_hub_be.permissions import IsAdminUser, IsParent, IsVolunteer

from .serializers import (
    AdminStatisticsSerializer,
    BabysitterDashboardStatisticsSerializer,
    BabysitterStatisticsSerializer,
    ParentDashboardStatisticsSerializer,
    ParentStatisticsSerializer,
)
from .services import (
    get_admin_statistics,
    get_babysitter_dashboard_statistics,
    get_babysitter_statistics,
    get_parent_dashboard_statistics,
    get_parent_statistics,
)


@extend_schema(tags=["Statistics"])
class ParentStatisticsView(APIView):
    """
    Get statistics for the authenticated parent.

    Returns booking counts, hours, spending, and most hired babysitter.
    Only accessible by users with role='parent'.
    """
    permission_classes = [IsAuthenticated, IsParent]

    @extend_schema(
        summary="Get parent statistics",
        description="Returns statistics for the authenticated parent's own data only.",
        responses={200: ParentStatisticsSerializer},
    )
    def get(self, request):
        stats = get_parent_statistics(request.user)
        serializer = ParentStatisticsSerializer(stats)
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class ParentDashboardView(APIView):
    """
    Get dashboard statistics for the authenticated parent with time filtering.

    Returns KPIs, charts data, babysitter analytics, and response metrics.
    Only accessible by users with role='parent'.

    Query params:
    - range: Number of days (7, 14, or 30). Defaults to 7.
    """
    permission_classes = [IsAuthenticated, IsParent]

    @extend_schema(
        summary="Get parent dashboard statistics",
        description="Returns dashboard statistics with time filtering. ?range=7|14|30",
        responses={200: ParentDashboardStatisticsSerializer},
    )
    def get(self, request):
        range_days = request.query_params.get('range', '7')
        try:
            range_days = int(range_days)
            if range_days not in [7, 14, 30]:
                range_days = 7
        except (ValueError, TypeError):
            range_days = 7

        stats = get_parent_dashboard_statistics(request.user, range_days)
        serializer = ParentDashboardStatisticsSerializer(stats)
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class BabysitterStatisticsView(APIView):
    """
    Get statistics for the authenticated babysitter.

    Returns job counts, hours worked, earnings, ratings, and repeat clients.
    Only accessible by users with role='babysitter'.
    """
    permission_classes = [IsAuthenticated, IsVolunteer]

    @extend_schema(
        summary="Get babysitter statistics",
        description="Returns statistics for the authenticated babysitter's own data only.",
        responses={200: BabysitterStatisticsSerializer},
    )
    def get(self, request):
        stats = get_babysitter_statistics(request.user)
        serializer = BabysitterStatisticsSerializer(stats)
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class BabysitterDashboardView(APIView):
    """
    Get dashboard statistics for the authenticated babysitter with time filtering.

    Returns KPIs, charts data, repeat clients stats, and optional metrics.
    Only accessible by users with role='babysitter'.

    Query params:
    - range: Number of days (7, 14, or 30). Defaults to 30.
    """
    permission_classes = [IsAuthenticated, IsVolunteer]

    @extend_schema(
        summary="Get babysitter dashboard statistics",
        description="Returns dashboard statistics with time filtering. ?range=7|14|30",
        responses={200: BabysitterDashboardStatisticsSerializer},
    )
    def get(self, request):
        range_days = request.query_params.get('range', '30')
        try:
            range_days = int(range_days)
            if range_days not in [7, 14, 30]:
                range_days = 30
        except (ValueError, TypeError):
            range_days = 30

        stats = get_babysitter_dashboard_statistics(request.user, range_days)
        serializer = BabysitterDashboardStatisticsSerializer(stats)
        return Response(serializer.data)


@extend_schema(tags=["Statistics"])
class AdminStatisticsView(APIView):
    """
    Get global platform statistics.

    Returns user metrics, booking metrics, completion rates, and trends.
    Only accessible by admin users (is_staff or is_superuser).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Get admin statistics",
        description="Returns global platform statistics. Admin only.",
        responses={200: AdminStatisticsSerializer},
    )
    def get(self, request):
        stats = get_admin_statistics()
        serializer = AdminStatisticsSerializer(stats)
        return Response(serializer.data)
