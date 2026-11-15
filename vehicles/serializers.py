import re

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Vehicle, VehicleEntry


class VehicleSerializer(serializers.ModelSerializer):
    vehicle_number = serializers.CharField(max_length=20)

    class Meta:
        model = Vehicle
        fields = ["id", "vehicle_number", "vehicle_type", "owner_name"]

    def validate_vehicle_number(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Vehicle number must not be blank.")

        duplicates = Vehicle.objects.filter(vehicle_number=value)
        if self.instance:  # updating: don't clash with ourselves
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                "A vehicle with this number already exists."
            )
        return value

class EntryCreateSerializer(serializers.Serializer):
    """Input only. Entry time and status are NOT fields, so clients cannot set them."""

    vehicle_number = serializers.CharField(max_length=20)
    vehicle_type = serializers.ChoiceField(choices=Vehicle.Type.choices)
    driver_name = serializers.CharField(max_length=100)
    driver_mobile = serializers.CharField(max_length=15)
    vendor_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    purpose = serializers.ChoiceField(choices=VehicleEntry.Purpose.choices)

    def validate_vehicle_number(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Vehicle number must not be blank.")
        return value

    def validate_driver_mobile(self, value):
        if not re.fullmatch(r"\d{10}", value):
            raise serializers.ValidationError(
                "Mobile number must contain exactly 10 digits."
            )
        return value

    def create(self, validated_data):
        number = validated_data.pop("vehicle_number")
        vehicle_type = validated_data.pop("vehicle_type")

        with transaction.atomic():  # outer: vehicle + entry succeed or fail together
            vehicle, created = Vehicle.objects.get_or_create(
                vehicle_number=number,
                defaults={"vehicle_type": vehicle_type},
            )

            if not created and vehicle.vehicle_type != vehicle_type:
                raise serializers.ValidationError(
                    {
                        "vehicle_type": (
                            f"This vehicle is registered as {vehicle.vehicle_type}. "
                            "Update it through the vehicle API if it has changed."
                        )
                    }
                )

            try:
                with transaction.atomic():  # inner: savepoint so we can catch the error
                    return VehicleEntry.objects.create(vehicle=vehicle, **validated_data)
            except IntegrityError:
                raise serializers.ValidationError(
                    {"error": "This vehicle is already inside the premises."}
                )


class EntryVehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "vehicle_number", "vehicle_type"]


class EntrySerializer(serializers.ModelSerializer):
    """Output: the entry with its nested vehicle."""

    vehicle = EntryVehicleSerializer(read_only=True)

    class Meta:
        model = VehicleEntry
        fields = [
            "id",
            "vehicle",
            "driver_name",
            "driver_mobile",
            "vendor_name",
            "purpose",
            "entry_time",
            "exit_time",
            "status",
        ]
        read_only_fields = fields