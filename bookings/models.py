from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        QUOTED = 'quoted', 'Quoted'
        ACCEPTED = 'accepted', 'Accepted'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    
    # trip info
    departure_city = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    arrival_date = models.DateField(null=True, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    
    # demographics
    adults = models.PositiveIntegerField(default=0)
    children = models.PositiveIntegerField(default=0)
    infants = models.PositiveIntegerField(default=0)
    
    # flags
    needs_flights = models.BooleanField(default=False)
    needs_hotel = models.BooleanField(default=False)
    needs_car = models.BooleanField(default=False)
    needs_guide = models.BooleanField(default=False)
    
    # context
    phone_number = models.CharField(max_length=20, blank=True)
    trip_purpose = models.CharField(max_length=255, blank=True)
    special_requests = models.TextField(blank=True)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING,
        db_index=True
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    # meta
    guest_info = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    quote_accepted_at = models.DateTimeField(null=True, blank=True)
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"booking {self.id} - {self.status}"

class BookingItem(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        RESERVED = 'reserved', 'Reserved'
        BOOKED = 'booked', 'Booked'
        CANCELLED = 'cancelled', 'Cancelled'

    class ItemType(models.TextChoices):
        FLIGHT = 'flight', 'Flight'
        HOTEL = 'hotel', 'Hotel'
        CAR = 'car', 'Car'
        ACTIVITY = 'activity', 'Activity'
        CUSTOM = 'custom', 'Custom'
        SERVICE = 'service', 'Service'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='booking_items')
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE, related_name='service_bookings', null=True, blank=True)
    booking = models.ForeignKey('Booking', on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    
    item_type = models.CharField(max_length=50, choices=ItemType.choices, default=ItemType.SERVICE)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    # timing
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # relational fields
    is_round_trip = models.BooleanField(default=False)
    return_date = models.DateField(null=True, blank=True)
    return_time = models.TimeField(null=True, blank=True)
    with_driver = models.BooleanField(default=False)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT,
        db_index=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.unit_price and self.quantity:
            self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

class Package(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        SELECTED = 'selected', 'Selected'
        PAID = 'paid', 'Paid'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='package')
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT,
        db_index=True
    )
    notes = models.TextField(blank=True, null=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"package for booking {self.booking.id}"

class PackageItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='items')
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service.title} in {self.package}"
