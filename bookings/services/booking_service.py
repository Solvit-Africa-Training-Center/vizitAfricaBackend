import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings

from accounts.models import User
from services.models import Service
from bookings.models import Booking, BookingItem
from accounts.utils.send_email import (
    send_itinerary_email,
    send_admin_trip_notification,
    send_client_quote_email,
    send_vendor_booking_request
)

logger = logging.getLogger(__name__)

class BookingService:
    @staticmethod
    @transaction.atomic
    def create_from_drafts(user: User) -> Booking:
        """Convert a user's draft items into a reserved booking."""
        draft_items = BookingItem.objects.filter(user=user, status='draft')
        
        if not draft_items.exists():
            raise ValidationError("No draft booking items found.")
            
        total_amount = sum(item.subtotal for item in draft_items)
        
        booking = Booking.objects.create(
            user=user,
            total_amount=total_amount,
            currency='USD',
            status='pending'
        )
        
        draft_items.update(booking=booking, status='reserved')
        return booking

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking: Booking, user: User) -> Booking:
        """Cancel a booking if allowed."""
        if booking.user != user and not user.is_staff:
             raise ValidationError("You do not have permission to cancel this booking.")
             
        if booking.status not in ['pending', 'quoted']:
            raise ValidationError(f"Cannot cancel booking in '{booking.status}' status.")

        booking.status = 'cancelled'
        booking.save()
        
        # Also cancel items
        booking.items.all().update(status='cancelled')
        
        return booking

    @staticmethod
    @transaction.atomic
    def confirm_quote(booking: Booking) -> Booking:
        """Confirm a quoted booking (usually by client)."""
        quote = booking.guest_info.get('packageQuote')
        if not quote or quote.get('status') != 'quoted':
            raise ValidationError("No valid quote found to confirm.")
            
        # Clear existing items
        booking.items.all().delete()
        
        # Create items from quote
        for item in quote.get('items', []):
            service_instance = None
            if item.get('service_id'):
                service_instance = Service.objects.filter(id=item.get('service_id')).first()
            
            BookingItem.objects.create(
                booking=booking,
                user=booking.user,
                service=service_instance,
                item_type=item.get('type', 'service'),
                title=item.get('title') or (service_instance.title if service_instance else 'Item'),
                description=item.get('description') or '',
                quantity=item.get('quantity', 1),
                unit_price=Decimal(str(item.get('unit_price', 0))),
                subtotal=Decimal(str(item.get('line_total', 0))),
                metadata=item.get('metadata', {}),
                status='booked',
                start_date=booking.guest_info.get('departureDate'),
                end_date=booking.guest_info.get('returnDate')
            )
            
        booking.status = 'confirmed'
        booking.save()
        
        # Mark quote accepted
        quote['status'] = 'accepted'
        quote['accepted_at'] = timezone.now().isoformat()
        booking.guest_info['packageQuote'] = quote
        booking.save()
        
        # Notify vendors
        try:
            send_vendor_booking_request(booking)
        except Exception as e:
            logger.error(f"Failed to send vendor booking requests for booking {booking.id}: {e}")
            
        return booking

class TripSubmissionService:
    @staticmethod
    def _candidate_external_ids(raw_id, item_type):
        if not raw_id: return []
        raw = str(raw_id).strip()
        item_type = str(item_type or "").lower()
        candidates = [raw]
        if raw.startswith(("fl-", "ht-", "car-", "gd-")): return candidates
        
        mapping = {
            "flight": "fl-",
            "hotel": "ht-", "accommodation": "ht-",
            "car": "car-", "car_rental": "car-", "transport": "car-",
            "guide": "gd-", "experience": "gd-", "tour": "gd-"
        }
        
        prefix = mapping.get(item_type)
        if prefix and raw.startswith(prefix[0]) and raw[1:].isdigit():
            candidates.append(f"{prefix}{raw[1:]}")
        return candidates

    @staticmethod
    def _resolve_service(item_data):
        external_id = item_data.get('service') or item_data.get('id')
        item_type = item_data.get('type')
        candidates = TripSubmissionService._candidate_external_ids(external_id, item_type)
        
        service = Service.objects.filter(external_id__in=candidates).first()
        if not service and item_data.get('title'):
            service = Service.objects.filter(title__iexact=item_data['title'].strip()).first()
        return service

    @staticmethod
    @transaction.atomic
    def process_submission(data: dict, request_user=None) -> Booking:
        """Process a complex trip submission from the guest form."""
        email = data.get('email')
        if not email:
            raise ValidationError({"email": "Email is required"})

        # 1. Handle User
        user = User.objects.filter(email=email).first()
        if user:
            if not request_user or not request_user.is_authenticated or request_user.email != email:
                 raise ValidationError("User with this email already exists. Please login to continue.")
        else:
            # Create guest user
            user = User.objects.create(
                email=email,
                full_name=data.get('name', 'Guest'),
                role='CLIENT',
                is_active=False
            )
            user.set_unusable_password()
            user.save()

        # 2. Limit check
        pending_count = Booking.objects.filter(user=user, status__in=['pending', 'quoted']).count()
        if pending_count >= 2:
            raise ValidationError("You have reached the limit of 2 pending trip requests.")

        # 3. Create Booking
        guest_info = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in data.items() if k != 'items'}
        guest_info['requestedItems'] = data.get('items', [])
        
        booking = Booking.objects.create(
            user=user,
            total_amount=Decimal('0.00'),
            currency='USD',
            status='pending',
            guest_info=guest_info
        )
        
        # 4. Process Items
        total = Decimal('0.00')
        items_data = data.get('items', [])
        email_items = []
        
        for item in items_data:
            if item.get('type') == 'note': continue
            
            service = TripSubmissionService._resolve_service(item)
            unit_price = service.base_price if service else Decimal(str(item.get('price', 0)))
            qty = item.get('quantity', 1)
            
            booking_item = BookingItem.objects.create(
                booking=booking,
                service=service,
                user=user,
                start_date=item.get('start_date') or data.get('departureDate'),
                end_date=item.get('end_date') or data.get('returnDate') or (item.get('start_date') or data.get('departureDate')),
                start_time=item.get('start_time'),
                end_time=item.get('end_time'),
                is_round_trip=item.get('is_round_trip', False),
                return_date=item.get('return_date'),
                quantity=qty,
                unit_price=unit_price,
                subtotal=unit_price * qty,
                status='reserved'
            )
            total += booking_item.subtotal
            
            email_items.append({
                'title': service.title if service else item.get('title', 'Service'),
                'type': item.get('type', 'experience'),
                'description': service.description if service else item.get('description', ''),
                'price': float(unit_price)
            })

        booking.total_amount = total
        booking.save()

        # 5. Notifications
        try:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            password_link = f"{frontend_url}/en/set-password?uidb64={uid}&token={token}"
            
            send_itinerary_email(user.email, user.full_name, email_items, password_link)
            send_admin_trip_notification(
                user.full_name, user.email, booking.id, email_items,
                {
                    'arrival': data['departureDate'].isoformat() if data.get('departureDate') else 'N/A',
                    'departure': data.get('returnDate').isoformat() if data.get('returnDate') else 'N/A'
                }
            )
        except Exception as e:
            logger.error(f"Failed to send submission notifications for booking {booking.id}: {e}")

        return booking
