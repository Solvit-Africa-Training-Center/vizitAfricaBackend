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
            'is_round_trip', 'return_date', 'return_time', 'quantity', 
            'unit_price', 'subtotal', 'status', 'metadata', 'created_at'
        ]
        read_only_fields = ['subtotal', 'created_at']
        extra_kwargs = {
            'service': {'required': False, 'allow_null': True},
            'start_date': {'required': False, 'allow_null': True},
            'end_date': {'required': False, 'allow_null': True},
        }
    
    def validate(self, data):
        start_date = data.get('start_date') or (self.instance.start_date if self.instance else None)
        end_date = data.get('end_date') or (self.instance.end_date if self.instance else None)
        
        if start_date and start_date < date.today():
            raise serializers.ValidationError("Start date cannot be in the past.")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("End date must be after start date.")
        return data

class GuestInfoMixin:
    """shared extraction of guest_info fields for both user and admin serializers"""

    def _info(self, obj):
        return obj.guest_info or {}

    def get_name(self, obj):
        return self._info(obj).get('name') or (obj.user.full_name if obj.user else "Guest")

    def get_email(self, obj):
        return self._info(obj).get('email') or (obj.user.email if obj.user else "")

    def get_phone(self, obj):
        return self._info(obj).get('phone') or (obj.user.phone_number if obj.user else "")

    def get_arrivalDate(self, obj):
        return self._info(obj).get('departureDate') or self._info(obj).get('arrivalDate')

    def get_departureDate(self, obj):
        return self._info(obj).get('returnDate') or self._info(obj).get('departureDate')

    def get_adults(self, obj):
        val = self._info(obj).get('adults', 0)
        return int(val) if val else 0

    def get_children(self, obj):
        val = self._info(obj).get('children', 0)
        return int(val) if val else 0

    def get_infants(self, obj):
        val = self._info(obj).get('infants', 0)
        return int(val) if val else 0

    def get_travelers(self, obj):
        return self.get_adults(obj) + self.get_children(obj) + self.get_infants(obj)

    def get_specialRequests(self, obj):
        return self._info(obj).get('specialRequests') or ""

    def get_tripPurpose(self, obj):
        return self._info(obj).get('tripPurpose') or ""

    def get_quote(self, obj):
        quote = self._info(obj).get('packageQuote')
        return quote if isinstance(quote, dict) else None

    def _requested_item_types(self, obj):
        booking_service_types = [
            item.service.service_type
            for item in obj.items.select_related('service').all()
            if item.service
        ]

        # Check explicit toggles from frontend if present
        info = self._info(obj)
        toggles = []
        if info.get('needsFlights'): toggles.append('flight')
        if info.get('needsHotel'): toggles.append('hotel')
        if info.get('needsCar'): toggles.append('car')
        if info.get('needsGuide'): toggles.append('guide')

        requested_items = info.get('requestedItems', [])
        requested_types = []
        for item in requested_items:
            item_type = str(item.get('type', '')).lower()
            if item_type and item_type != 'service':
                requested_types.append(item_type)
                continue

            category = str(item.get('category', '')).lower()
            title = str(item.get('title', '')).lower()
            combined = f"{category} {title}"
            if 'flight' in combined or 'air' in combined:
                requested_types.append('flight')
            elif 'hotel' in combined or 'bnb' in combined or 'retreat' in combined:
                requested_types.append('hotel')
            elif 'car' in combined or 'rental' in combined or 'land cruiser' in combined:
                requested_types.append('car')
            elif 'guide' in combined or 'tour' in combined or 'experience' in combined:
                requested_types.append('guide')
            else:
                requested_types.append('service')

        return booking_service_types + requested_types + toggles

    def get_needsFlights(self, obj):
        return self._info(obj).get('needsFlights', False) or any(t == 'flight' for t in self._requested_item_types(obj))

    def get_needsHotel(self, obj):
        return self._info(obj).get('needsHotel', False) or any(t in ['hotel', 'accommodation'] for t in self._requested_item_types(obj))

    def get_needsCar(self, obj):
        return self._info(obj).get('needsCar', False) or any(t in ['car', 'car_rental', 'transport'] for t in self._requested_item_types(obj))

    def get_needsGuide(self, obj):
        return self._info(obj).get('needsGuide', False) or any(t in ['experience', 'guide', 'tour'] for t in self._requested_item_types(obj))


class BookingSerializer(GuestInfoMixin, serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    arrivalDate = serializers.SerializerMethodField()
    departureDate = serializers.SerializerMethodField()
    travelers = serializers.SerializerMethodField()
    adults = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    infants = serializers.SerializerMethodField()
    needsFlights = serializers.SerializerMethodField()
    needsHotel = serializers.SerializerMethodField()
    needsCar = serializers.SerializerMethodField()
    needsGuide = serializers.SerializerMethodField()
    specialRequests = serializers.SerializerMethodField()
    tripPurpose = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'name', 'email', 'phone',
            'arrivalDate', 'departureDate',
            'travelers', 'adults', 'children', 'infants',
            'needsFlights', 'needsHotel', 'needsCar', 'needsGuide',
            'status', 'currency', 'total_amount',
            'specialRequests', 'tripPurpose',
            'items', 'quote', 'createdAt',
        ]
        read_only_fields = ['total_amount', 'created_at']


class TripSubmissionSerializer(serializers.Serializer):

    departureCity = serializers.CharField()
    destination = serializers.CharField(required=False, allow_blank=True)
    
    # Dates
    arrivalDate = serializers.DateField(required=False, allow_null=True)
    departureDate = serializers.DateField()
    returnDate = serializers.DateField(required=False, allow_null=True)
    
    # New Timing Fields
    arrivalTime = serializers.TimeField(required=False, allow_null=True)
    departureTime = serializers.TimeField(required=False, allow_null=True)
    returnTime = serializers.TimeField(required=False, allow_null=True)
    
    roundTrip = serializers.BooleanField(default=False)
    isRoundTrip = serializers.BooleanField(required=False)

    # Demographics
    adults = serializers.IntegerField(default=0)
    children = serializers.IntegerField(default=0)
    infants = serializers.IntegerField(default=0)

    # User Info
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    
    # Trip Context
    tripPurpose = serializers.CharField(required=False, allow_blank=True)
    specialRequests = serializers.CharField(required=False, allow_blank=True)

    # Service Requirements
    needsFlights = serializers.BooleanField(default=False)
    needsHotel = serializers.BooleanField(default=False)
    needsCar = serializers.BooleanField(default=False)
    needsGuide = serializers.BooleanField(default=False)

    # Professional Preferences
    preferredCabinClass = serializers.CharField(required=False, allow_blank=True)
    hotelStarRating = serializers.CharField(required=False, allow_blank=True)
    carTypePreference = serializers.CharField(required=False, allow_blank=True)
    budgetBracket = serializers.CharField(required=False, allow_blank=True)
    guideLanguages = serializers.ListField(child=serializers.CharField(), required=False)

    items = serializers.ListField(child=serializers.DictField())

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value

class AdminBookingItemSerializer(serializers.ModelSerializer):
    service_details = serializers.SerializerMethodField()

    class Meta:
        model = BookingItem
        fields = [
            'id', 'service', 'item_type', 'title', 'description',
            'start_date', 'end_date', 'start_time', 'end_time', 
            'is_round_trip', 'return_date', 'return_time', 'quantity', 'unit_price', 'subtotal',
            'metadata', 'service_details'
        ]
        read_only_fields = ['subtotal']

    def get_service_details(self, obj):
        from services.serializers import ServiceSerializer
        if obj.service:
            return ServiceSerializer(obj.service).data
        return None

class AdminBookingSerializer(GuestInfoMixin, serializers.ModelSerializer):
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

    notes = serializers.SerializerMethodField()
    specialRequests = serializers.SerializerMethodField()
    tripPurpose = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    adults = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    infants = serializers.SerializerMethodField()
    requestedItems = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()
    items = AdminBookingItemSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'name', 'email', 'phone', 'arrivalDate', 'departureDate',
            'travelers', 'adults', 'children', 'infants',
            'needsFlights', 'needsHotel', 'needsCar', 'needsGuide',
            'status', 'notes', 'specialRequests', 'tripPurpose', 'createdAt', 'items',
            'requestedItems', 'quote'
        ]

    def get_notes(self, obj):
        return self._info(obj).get('specialRequests') or ""

    def get_requestedItems(self, obj):
        booking_items = [
            {
                'id': str(item.id),
                'service': str(item.service_id),
                'type': item.service.service_type if item.service else 'service',
                'title': item.service.title if item.service else 'Service',
                'description': item.service.description if item.service else '',
                'price': item.unit_price,
                'quantity': item.quantity,
            }
            for item in obj.items.select_related('service').all()
            if item.service
        ]

        guest_items = self._info(obj).get('requestedItems', []) or []
        seen = {
            (
                str(item.get('service') or '').lower(),
                str(item.get('type') or '').lower(),
                str(item.get('title') or '').strip().lower(),
            )
            for item in booking_items
        }

        merged = list(booking_items)
        for item in guest_items:
            key = (
                str(item.get('service') or '').lower(),
                str(item.get('type') or '').lower(),
                str(item.get('title') or '').strip().lower(),
            )
            if key in seen:
                continue
            merged.append(item)
            seen.add(key)

        return merged

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
