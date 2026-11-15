from django.shortcuts import render

# Create your views here.
from rest_framework import mixins, viewsets

from .models import Vehicle
from .serializers import VehicleSerializer


class VehicleViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Create, list, retrieve and update vehicles. No delete (not required)."""

    queryset = Vehicle.objects.all().order_by("id")
    serializer_class = VehicleSerializer