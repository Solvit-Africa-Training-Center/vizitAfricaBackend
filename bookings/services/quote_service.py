import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from bookings.models import Booking, BookingItem
from services.models import Service

logger = logging.getLogger(__name__)

class QuoteService:
    @staticmethod
    def _resolve_service(item_data):
        # resolve service by id or title
        service_id = item_data.get('service_id') or item_data.get('service') or item_data.get('id')
        if not service_id: return None
        
        service = Service.objects.filter(id=service_id).first() or \
                  Service.objects.filter(external_id=service_id).first()
                  
        if not service and item_data.get('title'):
            service = Service.objects.filter(title__iexact=str(item_data['title']).strip()).first()
        return service

    @staticmethod
    @transaction.atomic
    def generate_quote(booking: Booking, items_data: list, admin_user) -> Booking:
        # update existing items with prices
        if not admin_user.is_staff:
            raise ValidationError("only admin can generate quotes")

        grand_total = Decimal('0.00')
        seen_item_ids = []
        
        for item in items_data:
            item_id = item.get('id')
            qty = int(item.get('quantity') or 1)
            price = Decimal(str(item.get('unit_price') or item.get('price') or 0))
            subtotal = qty * price
            grand_total += subtotal
            
            service = QuoteService._resolve_service(item)
            
            defaults = {
                'service': service,
                'title': item.get('title') or (service.title if service else 'service'),
                'description': item.get('description') or (service.description if service else ''),
                'item_type': item.get('type') or item.get('item_type') or 'service',
                'start_date': item.get('start_date') or item.get('startDate'),
                'end_date': item.get('end_date') or item.get('endDate'),
                'start_time': item.get('start_time') or item.get('startTime'),
                'end_time': item.get('end_time') or item.get('endTime'),
                'is_round_trip': item.get('is_round_trip', item.get('isRoundTrip', False)),
                'return_date': item.get('return_date') or item.get('returnDate'),
                'return_time': item.get('return_time') or item.get('returnTime'),
                'with_driver': item.get('with_driver', item.get('withDriver', False)),
                'quantity': qty,
                'unit_price': price,
                'subtotal': subtotal,
                'status': BookingItem.Status.RESERVED
            }
            
            valid_id = None
            if item_id:
                try:
                    valid_id = uuid.UUID(str(item_id))
                except ValueError:
                    valid_id = None

            booking_item, created = BookingItem.objects.update_or_create(
                id=valid_id if valid_id else uuid.uuid4(),
                booking=booking,
                user=booking.user,
                defaults=defaults
            )
            seen_item_ids.append(booking_item.id)
            
        # remove items not in quote
        booking.items.exclude(id__in=seen_item_ids).delete()
        
        # finalize booking
        booking.status = Booking.Status.QUOTED
        booking.total_amount = grand_total
        booking.save()
        
        return booking
