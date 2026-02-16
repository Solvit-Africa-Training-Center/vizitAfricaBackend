from rest_framework import serializers
from .models import BookingItem, Booking
from datetime import date

class BookingItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = BookingItem
        fields = [
            'id', 'service', 'start_date', 'end_date', 'quantity', 
            'unit_price', 'subtotal', 'status', 'created_at'
        ]
        read_only_fields = ['subtotal', 'created_at']
    
    def validate(self, data):
        start_date = data.get('start_date') or (self.instance.start_date if self.instance else None)
        end_date = data.get('end_date') or (self.instance.end_date if self.instance else None)
        
        if start_date and start_date < date.today():
            raise serializers.ValidationError("Start date cannot be in the past.")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("End date must be after start date.")
        return data

class BookingSerializer(serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'total_amount', 'currency', 'status', 'items', 'created_at', 'updated_at']
        read_only_fields = ['total_amount', 'created_at', 'updated_at']

class TripSubmissionSerializer(serializers.Serializer):
    
    departureCity = serializers.CharField()
    destination = serializers.CharField(required=False, allow_blank=True)
    departureDate = serializers.DateField()
    returnDate = serializers.DateField(required=False, allow_null=True)
    adults = serializers.IntegerField()
    children = serializers.IntegerField()
    infants = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    tripPurpose = serializers.CharField()
    specialRequests = serializers.CharField(required=False, allow_blank=True)
    
    
    items = serializers.ListField(child=serializers.DictField())

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

class AdminBookingSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    arrivalDate = serializers.SerializerMethodField()
    departureDate = serializers.SerializerMethodField()
    travelers = serializers.SerializerMethodField()
    needsFlights = serializers.SerializerMethodField()
    needsHotel = serializers.SerializerMethodField()
    needsCar = serializers.SerializerMethodField()
    needsGuide = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'name', 'email', 'arrivalDate', 'departureDate', 
            'travelers', 'needsFlights', 'needsHotel', 'needsCar', 
            'needsGuide', 'status', 'createdAt'
        ]

    def get_name(self, obj):
        return obj.guest_info.get('name') or obj.user.full_name

    def get_email(self, obj):
        return obj.guest_info.get('email') or obj.user.email

    def get_arrivalDate(self, obj):
        return obj.guest_info.get('departureDate')

    def get_departureDate(self, obj):
        return obj.guest_info.get('returnDate')
    
    def get_travelers(self, obj):
        # Sum of adults, children, infants from guest_info
        adults = int(obj.guest_info.get('adults', 0) or 0)
        children = int(obj.guest_info.get('children', 0) or 0)
        infants = int(obj.guest_info.get('infants', 0) or 0)
        return adults + children + infants

    def get_needsFlights(self, obj):
        return any(item.service.service_type == 'flight' for item in obj.items.all() if item.service)

    def get_needsHotel(self, obj):
        return any(item.service.service_type == 'hotel' for item in obj.items.all() if item.service)

    def get_needsCar(self, obj):
        return any(item.service.service_type == 'car_rental' for item in obj.items.all() if item.service)

    def get_needsGuide(self, obj):
        return any(item.service.service_type == 'experience' for item in obj.items.all() if item.service)