from rest_framework import serializers
from .models import Transaction

class TransactionSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'booking_id', 'user_name', 'amount', 'currency', 
                 'transaction_type', 'status', 'created_at']
        read_only_fields = ['created_at']
