from rest_framework import serializers

from .models import Vehicle


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