from django.contrib import admin
from .models import BookingItem, Booking

@admin.register(BookingItem)
class BookingItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'service_id', 'item_type', 'title', 'quantity', 'unit_price', 'subtotal', 'status', 'created_at']
    list_filter = ['status', 'item_type', 'created_at']
    search_fields = ['user__email', 'title', 'service__title']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'departure_city', 'arrival_date', 'departure_date', 'total_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'needs_flights', 'needs_hotel', 'needs_car', 'needs_guide']
    search_fields = ['user__email', 'departure_city', 'destination']