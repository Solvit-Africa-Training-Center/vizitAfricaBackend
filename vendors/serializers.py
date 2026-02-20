from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from .models import Vendor
from django.db import transaction
from accounts.models import User

class VendorSerializer(ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    bio = serializers.CharField(source='user.bio', read_only=True)

    class Meta:
        model = Vendor
        fields = [
            'id', 'business_name', 'address', 'website', 'vendor_type', 
            'is_approved', 'approved_by', 'approved_on', 'user', 
            'email', 'full_name', 'phone_number', 'bio'
        ]
        read_only_fields = ['is_approved', 'approved_by', 'approved_on', 'user']

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('email')
        full_name = validated_data.pop('full_name')
        phone_number = validated_data.pop('phone_number', '')
        bio = validated_data.pop('bio', '')

        # Check if user exists
        user = User.objects.filter(email=email).first()
        
        if not user:
            # Create placeholder user
            from django.utils.crypto import get_random_string
            user = User.objects.create_user(
                email=email,
                full_name=full_name,
                phone_number=phone_number,
                password=get_random_string(12),
                is_active=False, # Not verified
                role=User.VENDOR,
                bio=bio
            )
            # We explicitly do NOT send verification email here as per requirement
        
        # Link vendor to user
        validated_data['user'] = user
        
        vendor = Vendor.objects.create(**validated_data)
        return vendor