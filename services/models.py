from django.db import models
from django.conf import settings

from vendors.models import Vendor

# Create your models here.


import uuid

class Service(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        PENDING = 'pending', 'Pending'
        DELETED = 'deleted', 'Deleted'

    class ServiceType(models.TextChoices):
        HOTEL = 'hotel', 'Hotel'
        CAR = 'car', 'Car'
        ACTIVITY = 'activity', 'Activity'
        EXPERIENCE = 'experience', 'Experience'
        TOUR = 'tour', 'Tour'
        GUIDE = 'guide', 'Guide'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='services')
    location = models.ForeignKey('locations.Location', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    service_type = models.CharField(max_length=50, choices=ServiceType.choices)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    capacity = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.ACTIVE,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.title


class ServiceMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='media')
    media_url = models.URLField()
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.service.title} - {self.media_type} #{self.sort_order}"


class ServiceAvailability(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='availabilities')
    start_date = models.DateField()
    end_date = models.DateField()
    available_quantity = models.IntegerField()
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.service.title} ({self.start_date} to {self.end_date})"


class Discount(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed Amount'

    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.code} - {self.name}"