from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from .models import Service, ServiceMedia, ServiceAvailability, Discount


class ServiceMediaSerializer(ModelSerializer):
    class Meta:
        model = ServiceMedia
        fields = "__all__"


class ServiceSerializer(ModelSerializer):
    media = ServiceMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = "__all__"
        read_only_fields = ['created_at']
        extra_kwargs = {
            'user': {'required': False, 'allow_null': True}
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
