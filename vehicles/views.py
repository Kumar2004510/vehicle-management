from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Vehicle, VehicleEntry
from .serializers import (
    EntryCreateSerializer,
    EntrySerializer,
    VehicleSerializer,
)


class VehicleViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Vehicle.objects.all().order_by("id")
    serializer_class = VehicleSerializer


class EntryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = VehicleEntry.objects.select_related("vehicle")
    serializer_class = EntrySerializer

    def get_serializer_class(self):
        if self.action == "create":
            return EntryCreateSerializer
        return EntrySerializer

    def create(self, request, *args, **kwargs):
        serializer = EntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(EntrySerializer(entry).data, status=status.HTTP_201_CREATED)