import logging
from decimal import Decimal
from django.utils import timezone
from bookings.models import Booking

logger = logging.getLogger(__name__)

class QuoteService:
    @staticmethod
    def generate_quote(booking: Booking, items_data: list, admin_user) -> Booking:
        """
        Generate or update a quote snapshot for a booking.
        """
        guest_info = booking.guest_info or {}
        
        grand_total = Decimal('0.00')
        normalized_items = []
        
        for item in items_data:
            qty = int(item.get('quantity') or 1)
            price = Decimal(str(item.get('unit_price') or 0))
            line_total = qty * price
            grand_total += line_total
            
            normalized_items.append({
                'id': item.get('id'), 
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
