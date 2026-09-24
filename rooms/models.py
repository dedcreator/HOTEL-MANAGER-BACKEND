# Create your models here.
# rooms/models.py
from django.db import models
import uuid

class Room(models.Model):
    ROOM_TYPES = (
        ('standard', 'Standard'),
        ('deluxe', 'Deluxe'),
        ('executive', 'Executive'),
        ('suite', 'Suite'),
    )
    
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=50, default='standard')
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    description = models.TextField(blank=True)
    capacity = models.IntegerField(default=2)
    is_short_rest_available = models.BooleanField(default=True, help_text="Designated for short rest")
    short_rest_price = models.DecimalField(max_digits=10, decimal_places=2, default=8000.00, help_text="Price for short rest")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.barcode:
            # Generate barcode from room number
            self.barcode = f"RM{self.room_number}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Room {self.room_number} - {self.room_type}"


class RoomTypeConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    default_base_price = models.DecimalField(max_digits=10, decimal_places=2, default=15000.00)
    default_short_rest_price = models.DecimalField(max_digits=10, decimal_places=2, default=8000.00)
    capacity = models.IntegerField(default=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RoomSettings(models.Model):
    default_short_rest_price = models.DecimalField(max_digits=10, decimal_places=2, default=8000.00)
    short_rest_duration_hours = models.IntegerField(default=2)
    short_rest_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(
                default_short_rest_price=8000.00,
                short_rest_duration_hours=2,
                short_rest_enabled=True,
            )
        return obj