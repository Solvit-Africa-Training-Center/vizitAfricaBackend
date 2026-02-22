from django.db import models
from django.conf import settings

class Vendor(models.Model):
    class VendorType(models.TextChoices):
        HOTEL = 'hotel', 'Hotel/Accommodation'
        CAR_RENTAL = 'car_rental', 'Car Rental'
        GUIDE = 'guide', 'Tour Guide'
        EXPERIENCE = 'experience', 'Experience Provider'
        TRANSPORT = 'transport', 'Transport Company'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        PENDING = 'pending', 'Pending'
        SUSPENDED = 'suspended', 'Suspended'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True, null=True)
    vendor_type = models.CharField(
        max_length=50, 
        choices=VendorType.choices, 
        default=VendorType.OTHER,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    is_system_user = models.BooleanField(default=True, help_text="True if they can log in to the dashboard")
    
    is_approved = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_vendors")
    approved_on = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.business_name} ({self.get_vendor_type_display()})"