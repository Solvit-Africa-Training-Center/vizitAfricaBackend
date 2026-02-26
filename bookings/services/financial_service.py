import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from bookings.models import Booking
from transactions.models import Transaction

logger = logging.getLogger(__name__)

class FinancialService:
    # This could be moved to settings or a DB configuration model
    DEFAULT_COMMISSION_RATE = Decimal('0.10')

    @staticmethod
    def process_commission(booking: Booking, rate: Decimal = None) -> Transaction:
        """Calculate and create commission transaction for a paid booking."""
        if booking.status != Booking.Status.PAID:
            raise ValidationError("Commission can only be processed for paid bookings.")
            
        if Transaction.objects.filter(booking=booking, transaction_type='commission').exists():
            return None # Already processed
            
        commission_rate = rate or FinancialService.DEFAULT_COMMISSION_RATE
        commission_amount = booking.total_amount * commission_rate
        
        return Transaction.objects.create(
            booking=booking,
            user=booking.user,
            amount=commission_amount,
            currency=booking.currency,
            transaction_type='commission',
            status='completed'
        )

    @staticmethod
    @transaction.atomic
    def process_refund(booking: Booking) -> Transaction:
        """Process full refund for a booking and cancel it."""
        if booking.status not in [Booking.Status.PAID, Booking.Status.COMPLETED]:
            raise ValidationError("Only paid or completed bookings can be refunded.")
            
        if Transaction.objects.filter(booking=booking, transaction_type='refund').exists():
            raise ValidationError("Booking already refunded.")
            
        # Create refund transaction
        refund_tx = Transaction.objects.create(
            booking=booking,
            user=booking.user,
            amount=booking.total_amount,
            currency=booking.currency,
            transaction_type='refund',
            status='pending'
        )
        
        # Update booking status
        booking.status = Booking.Status.CANCELLED
        booking.save()
        
        # Cancel items
        booking.items.all().update(status='cancelled')
        
        return refund_tx

    @staticmethod
    def process_payout(booking: Booking) -> Transaction:
        """Calculate and process payout to vendor."""
        if booking.status != Booking.Status.PAID:
             raise ValidationError("Payout can only be processed for paid bookings.")

        if Transaction.objects.filter(booking=booking, transaction_type='payout').exists():
            return None # Already processed

        # Groups by vendor if needed, for now picking the first vendor as primary
        booking_item = booking.items.all().first()
        if not booking_item or not booking_item.service or not booking_item.service.user:
            raise ValidationError("No vendor found for this booking.")
            
        vendor = booking_item.service.user
        
        commission_rate = FinancialService.DEFAULT_COMMISSION_RATE
        payout_amount = booking.total_amount * (Decimal('1.00') - commission_rate)
        
        return Transaction.objects.create(
            booking=booking,
            user=vendor,
            amount=payout_amount,
            currency=booking.currency,
            transaction_type='payout',
            status='completed'
        )
