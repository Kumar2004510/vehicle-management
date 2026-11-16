from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
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
    serializer_class = EntrySerializer

    def get_queryset(self):
        qs = VehicleEntry.objects.select_related("vehicle").order_by("-entry_time")
        params = self.request.query_params

        vehicle_number = params.get("vehicle_number")
        if vehicle_number:
            qs = qs.filter(vehicle__vehicle_number=vehicle_number.strip().upper())

        status_value = params.get("status")
        if status_value:
            status_value = status_value.strip().upper()
            if status_value not in VehicleEntry.Status.values:
                raise ValidationError({"status": "Must be INSIDE or EXITED."})
            qs = qs.filter(status=status_value)

        date_value = params.get("date")
        if date_value:
            parsed = parse_date(date_value)
            if parsed is None:
                raise ValidationError({"date": "Use the format YYYY-MM-DD."})
            qs = qs.filter(entry_time__date=parsed)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return EntryCreateSerializer
        return EntrySerializer

    def create(self, request, *args, **kwargs):
        serializer = EntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(EntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="inside")
    def inside(self, request):
        entries = VehicleEntry.objects.filter(
            status=VehicleEntry.Status.INSIDE
        ).select_related("vehicle").order_by("entry_time")
        vehicles = [
            {
                "entry_id": e.id,
                "vehicle_number": e.vehicle.vehicle_number,
                "driver_name": e.driver_name,
                "entry_time": e.entry_time,
                "status": e.status,
            }
            for e in entries
        ]
        return Response({"total_inside": len(vehicles), "vehicles": vehicles})

    @action(detail=True, methods=["post"], url_path="exit")
    def exit_entry(self, request, pk=None):
        with transaction.atomic():
            entry = get_object_or_404(
                VehicleEntry.objects.select_for_update(of=("self",)).select_related(
                    "vehicle"
                ),
                pk=pk,
            )

            if entry.status == VehicleEntry.Status.EXITED:
                return Response(
                    {"error": "This vehicle has already exited."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            now = timezone.now()
            if now < entry.entry_time:
                return Response(
                    {"error": "Exit time cannot be earlier than entry time."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            entry.exit_time = now
            entry.status = VehicleEntry.Status.EXITED
            entry.save(update_fields=["exit_time", "status"])

        return Response(
            {
                "id": entry.id,
                "vehicle_number": entry.vehicle.vehicle_number,
                "entry_time": entry.entry_time,
                "exit_time": entry.exit_time,
                "status": entry.status,
                "duration_minutes": entry.duration_minutes,
            },
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
def daily_report(request):
    date_value = request.query_params.get("date")
    if not date_value:
        raise ValidationError({"date": "This query parameter is required (YYYY-MM-DD)."})
    report_date = parse_date(date_value)
    if report_date is None:
        raise ValidationError({"date": "Use the format YYYY-MM-DD."})

    # Three independent counts: do not derive one from another.
    total_entries = VehicleEntry.objects.filter(entry_time__date=report_date).count()
    total_exits = VehicleEntry.objects.filter(exit_time__date=report_date).count()
    currently_inside = VehicleEntry.objects.filter(
        status=VehicleEntry.Status.INSIDE
    ).count()

    return Response(
        {
            "date": report_date.isoformat(),
            "total_entries": total_entries,
            "total_exits": total_exits,
            "currently_inside": currently_inside,
        }
    )