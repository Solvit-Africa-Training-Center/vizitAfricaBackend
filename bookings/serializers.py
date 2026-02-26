from rest_framework import serializers
from .models import BookingItem, Booking, Package, PackageItem
from datetime import date

class BookingItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = BookingItem
        fields = [
            'id', 'service', 'item_type', 'title', 'description', 
            'start_date', 'end_date', 'start_time', 'end_time', 
            'is_round_trip', 'return_date', 'return_time', 'with_driver',
            'quantity', 'unit_price', 'subtotal', 'status', 'metadata', 'created_at'
        ]
        read_only_fields = ['subtotal', 'created_at']

class BookingSerializer(serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'status', 'payment_status', 'currency', 'total_amount',
            'departure_city', 'destination', 'arrival_date', 'departure_date',
            'adults', 'children', 'infants',
            'needs_flights', 'needs_hotel', 'needs_car', 'needs_guide',
            'phone_number', 'trip_purpose', 'special_requests',
            'items', 'quote_accepted_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['total_amount', 'created_at', 'updated_at']

class TripSubmissionSerializer(serializers.ModelSerializer):
    # accepts strict snake_case from frontend
    name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    items = serializers.ListField(child=serializers.DictField(), write_only=True)

    class Meta:
        model = Booking
        fields = [
            'name', 'email', 'phone_number', 
            'departure_city', 'destination', 'arrival_date', 'departure_date',
            'adults', 'children', 'infants',
            'needs_flights', 'needs_hotel', 'needs_car', 'needs_guide',
            'trip_purpose', 'special_requests', 'items'
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("at least one item is required")
        return value


class AdminBookingItemSerializer(serializers.ModelSerializer):
    service_details = serializers.SerializerMethodField()

    class Meta:
        model = BookingItem
        fields = [
            'id', 'service', 'item_type', 'title', 'description',
            'start_date', 'end_date', 'start_time', 'end_time', 
            'is_round_trip', 'return_date', 'return_time', 'with_driver',
            'quantity', 'unit_price', 'subtotal',
            'metadata', 'service_details'
        ]
        read_only_fields = ['subtotal']

    def get_service_details(self, obj):
        from services.serializers import ServiceSerializer
        if obj.service:
            return ServiceSerializer(obj.service).data
        return None

class AdminBookingSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    items = AdminBookingItemSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'name', 'email', 'phone_number', 
            'departure_city', 'destination', 'arrival_date', 'departure_date',
            'adults', 'children', 'infants',
            'needs_flights', 'needs_hotel', 'needs_car', 'needs_guide',
            'status', 'payment_status', 'currency', 'total_amount',
            'trip_purpose', 'special_requests', 
            'items', 'quote_accepted_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['total_amount', 'created_at', 'updated_at']

class PackageItemSerializer(serializers.ModelSerializer):
    service_details = serializers.SerializerMethodField()

    class Meta:
        model = PackageItem
        fields = ['id', 'service', 'price_override', 'notes', 'service_details']

    def get_service_details(self, obj):
        from services.serializers import ServiceSerializer
        return ServiceSerializer(obj.service).data

class PackageSerializer(serializers.ModelSerializer):
    items = PackageItemSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = ['id', 'booking', 'status', 'notes', 'expires_at', 'items', 'created_at', 'updated_at']
