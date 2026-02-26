
from rest_framework import serializers
from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'country', 'region', 'description', 'latitude', 'longitude', 'created_at']
        read_only_fields = ['id', 'created_at']