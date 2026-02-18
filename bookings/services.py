from django.db import transaction
from django.utils import timezone
from .models import Booking, BookingItem
from services.models import Service
from decimal import Decimal

class QuoteService:
    @staticmethod
    def generate_quote(booking, items_data, admin_user):
        """
        Generate or update a quote for a booking.
        items_data: List of dicts with item details
        """
        # Save quote snapshot in guest_info (legacy support + ease of access)
        guest_info = booking.guest_info or {}
        
        # Calculate totals
        grand_total = Decimal('0.00')
        normalized_items = []
        
        for item in items_data:
            qty = int(item.get('quantity') or 1)
            price = Decimal(str(item.get('unit_price') or 0))
            line_total = qty * price
            grand_total += line_total
            
            normalized_items.append({
                'id': item.get('id'), # temporary ID if new
                'service_id': item.get('service_id'),
                'type': item.get('type') or 'custom',
                'title': item.get('title'),
                'description': item.get('description'),
                'quantity': qty,
                'unit_price': float(price),
                'line_total': float(line_total),
                'metadata': item.get('metadata', {})
            })
            
        quote_data = {
            'status': 'quoted',
            'sent_at': timezone.now().isoformat(),
            'sent_by': str(admin_user.id),
            'currency': booking.currency,
            'total_amount': float(grand_total),
            'items': normalized_items,
            'notes': items_data[0].get('quote_notes', '') if items_data else ''
        }
        
        guest_info['packageQuote'] = quote_data
        booking.guest_info = guest_info
        booking.status = 'quoted'
        booking.total_amount = grand_total
        booking.save()
        
        return booking

class BookingService:
    @staticmethod
    @transaction.atomic
    def confirm_booking(booking):
        """
        Convert a quoted booking into a confirmed booking with real BookingItems.
        """
        quote = booking.guest_info.get('packageQuote')
        if not quote or quote.get('status') != 'quoted':
            raise ValueError("No valid quote found to confirm")
            
        # 1. Clear existing items to prevent duplicates if re-confirming
        booking.items.all().delete()
        
        # 2. Create actual BookingItems from quote
        for item in quote.get('items', []):
            service_instance = None
            if item.get('service_id'):
                service_instance = Service.objects.filter(id=item.get('service_id')).first()
            
            BookingItem.objects.create(
                booking=booking,
                user=booking.user,
                service=service_instance,
                item_type=item.get('type', 'custom'),
                title=item.get('title') or (service_instance.title if service_instance else 'Custom Item'),
                description=item.get('description', ''),
                quantity=item.get('quantity', 1),
                unit_price=Decimal(str(item.get('unit_price', 0))),
                subtotal=Decimal(str(item.get('line_total', 0))),
                metadata=item.get('metadata', {}),
                status='booked',
                start_date=booking.guest_info.get('departureDate') or timezone.now().date(), # Fallbacks
                end_date=booking.guest_info.get('returnDate') or timezone.now().date()
            )
            
        # 3. Update Booking Status
        booking.status = 'confirmed'
        booking.save()
        
        # 4. Mark quote as accepted
        quote['status'] = 'accepted'
        quote['accepted_at'] = timezone.now().isoformat()
        booking.guest_info['packageQuote'] = quote
        booking.save()
        
        return booking


from transactions.models import Transaction

class FinancialService:
    COMMISSION_RATE = Decimal('0.10')

    @staticmethod
    def process_commission(booking):
        """
        Calculate and create commission transaction for a confirmed booking.
        """
        if booking.status != 'confirmed':
            raise ValueError("Commission can only be processed for confirmed bookings")
            
        if Transaction.objects.filter(booking=booking, transaction_type='commission').exists():
            return None # Already processed
            
        commission_amount = booking.total_amount * FinancialService.COMMISSION_RATE
        
        return Transaction.objects.create(
            booking=booking,
            user=booking.user,
            amount=commission_amount,
            currency=booking.currency,
            transaction_type='commission',
            status='completed'
        )

    @staticmethod
    def process_refund(booking):
        """
        Process full refund for a booking and cancel it.
        """
        if booking.status != 'confirmed':
            raise ValueError("Only confirmed bookings can be refunded")
            
        if Transaction.objects.filter(booking=booking, transaction_type='refund').exists():
            raise ValueError("Booking already refunded")
            
        with transaction.atomic():
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
            booking.status = 'cancelled'
            booking.save()
            
            return refund_tx

    @staticmethod
    def process_payout(booking):
        """
        Calculate and process payout to vendor.
        """
        if booking.status != 'confirmed':
            raise ValueError("Payout can only be processed for confirmed bookings")

        if Transaction.objects.filter(booking=booking, transaction_type='payout').exists():
            return None # Already processed

        # Get the service owner (vendor) from booking items
        # Assuming all items in a booking belong to the same vendor for now
        # or we pick the first one as the primary vendor
        booking_items = booking.items.all()
        if not booking_items.exists():
            raise ValueError("No booking items found")
            
        vendor = booking_items.first().service.user
        
        commission_rate = FinancialService.COMMISSION_RATE
        payout_amount = booking.total_amount * (Decimal('1.00') - commission_rate)
        
        return Transaction.objects.create(
            booking=booking,
            user=vendor,
            amount=payout_amount,
            currency=booking.currency,
            transaction_type='payout',
            status='completed'
        )
