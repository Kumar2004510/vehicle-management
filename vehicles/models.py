from django.db import models
from django.db.models import Q
from django.utils import timezone


class Vehicle(models.Model):
    class Type(models.TextChoices):
        TWO_WHEELER = "TWO_WHEELER"
        CAR = "CAR"
        TRUCK = "TRUCK"
        OTHER = "OTHER"

    vehicle_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=Type.choices)
    owner_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.vehicle_number = self.vehicle_number.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.vehicle_number


class VehicleEntry(models.Model):
    class Purpose(models.TextChoices):
        MATERIAL_DELIVERY = "MATERIAL_DELIVERY"
        PICKUP = "PICKUP"
        VISITOR = "VISITOR"
        OTHER = "OTHER"

    class Status(models.TextChoices):
        INSIDE = "INSIDE"
        EXITED = "EXITED"

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="entries"
    )
    driver_name = models.CharField(max_length=100)
    driver_mobile = models.CharField(max_length=15)
    vendor_name = models.CharField(max_length=100, blank=True)
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    entry_time = models.DateTimeField(default=timezone.now)
    exit_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.INSIDE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=Q(status="INSIDE"),
                name="one_active_entry_per_vehicle",
            ),
            models.CheckConstraint(
                condition=Q(exit_time__isnull=True)
                | Q(exit_time__gte=models.F("entry_time")),
                name="exit_not_before_entry",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["entry_time"]),
            models.Index(fields=["exit_time"]),
        ]

    @property
    def duration_minutes(self):
        if self.exit_time:
            return int((self.exit_time - self.entry_time).total_seconds() // 60)
        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.exit_time and self.entry_time and self.exit_time < self.entry_time:
            raise ValidationError("Exit time cannot be earlier than entry time.")

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.status}"