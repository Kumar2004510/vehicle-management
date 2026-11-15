from rest_framework.routers import DefaultRouter

from .views import EntryViewSet, VehicleViewSet

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("entries", EntryViewSet, basename="entry")

urlpatterns = router.urls