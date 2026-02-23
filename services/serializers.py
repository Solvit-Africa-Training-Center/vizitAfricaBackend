from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from .models import Service, ServiceMedia, ServiceAvailability, Discount


class ServiceMediaSerializer(ModelSerializer):
    class Meta:
        model = ServiceMedia
        fields = ['id', 'media_url', 'media_type', 'sort_order']


class VendorBriefSerializer(serializers.Serializer):
    """minimal vendor info for service listings"""
    id = serializers.IntegerField(source='user.vendor_profile.id', read_only=True)
    business_name = serializers.CharField(source='user.vendor_profile.business_name', read_only=True)
    is_approved = serializers.BooleanField(source='user.vendor_profile.is_approved', read_only=True)

    def to_representation(self, instance):
        vendor = getattr(instance, 'vendor_profile', None)
        if not vendor:
            return None
        return {
            'id': str(vendor.id),
            'business_name': vendor.business_name,
            'is_approved': vendor.is_approved,
        }


class ServiceSerializer(ModelSerializer):
    media = ServiceMediaSerializer(many=True, read_only=True)
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            'id', 'title', 'service_type', 'description', 'base_price',
            'currency', 'capacity', 'status', 'location', 'user',
            'external_id', 'metadata', 'media', 'vendor', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'user': {'required': False, 'allow_null': True}
        }

    def get_vendor(self, obj):
        vendor = getattr(obj.user, 'vendor_profile', None)
        if not vendor:
            return None
        return {
            'id': str(vendor.id),
            'business_name': vendor.business_name,
            'is_approved': vendor.is_approved,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            from accounts.models import User
            if not (hasattr(request.user, 'role') and request.user.role == User.ADMIN):
                self.fields['user'].read_only = True


class ServiceAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAvailability
        fields = '__all__'


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = '__all__'
