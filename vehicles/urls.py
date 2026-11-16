from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EntryViewSet, VehicleViewSet, daily_report

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("entries", EntryViewSet, basename="entry")

urlpatterns = [
    path("reports/daily/", daily_report, name="daily-report"),
] + router.urls