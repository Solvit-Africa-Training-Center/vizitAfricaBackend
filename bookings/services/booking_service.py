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
        # convert draft items to a pending booking
        draft_items = BookingItem.objects.filter(user=user, status=BookingItem.Status.DRAFT)
        
        if not draft_items.exists():
            raise ValidationError("no draft items found")
            
        total_amount = sum(item.subtotal for item in draft_items)
        
        booking = Booking.objects.create(
            user=user,
            total_amount=total_amount,
            currency='USD',
            status=Booking.Status.PENDING
        )
        
        draft_items.update(booking=booking, status=BookingItem.Status.RESERVED)
        return booking

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking: Booking, user: User) -> Booking:
        # cancel booking if allowed
        if booking.user != user and not user.is_staff:
             raise ValidationError("you do not have permission to cancel this booking")
             
        if booking.status not in [Booking.Status.PENDING, Booking.Status.QUOTED]:
            raise ValidationError(f"cannot cancel booking in '{booking.status}' status")

        booking.status = Booking.Status.CANCELLED
        booking.save()
        booking.items.all().update(status=BookingItem.Status.CANCELLED)
        return booking

    @staticmethod
    @transaction.atomic
    def confirm_quote(booking: Booking) -> Booking:
        # confirm quoted booking
        if booking.status != Booking.Status.QUOTED:
            raise ValidationError("no valid quote found to confirm")
            
        booking.status = Booking.Status.ACCEPTED
        booking.quote_accepted_at = timezone.now()
        booking.save()
        
        # mark items as booked
        booking.items.all().update(status=BookingItem.Status.BOOKED)
        
        try:
            send_vendor_booking_request(booking)
        except Exception as e:
            logger.error(f"failed to send vendor booking requests: {e}")
            
        return booking

class TripSubmissionService:
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
    def _send_submission_notifications(user, booking, email_items, data, is_new_user=False):
        try:
            password_link = None
            if is_new_user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                password_link = f"{frontend_url}/en/set-password?uidb64={uid}&token={token}"
            
            send_itinerary_email(user.email, user.full_name, email_items, password_link)
            send_admin_trip_notification(
                user.full_name, user.email, booking.id, email_items,
                {
                    'arrival': booking.arrival_date.isoformat() if booking.arrival_date else 'n/a',
                    'departure': booking.departure_date.isoformat() if booking.departure_date else 'n/a'
                }
            )
        except Exception as e:
            logger.error(f"failed to send notifications: {e}")

    @staticmethod
    @transaction.atomic
    def process_submission(data: dict, request_user=None) -> Booking:
        # process trip submission
        email = data.get('email')
        name = data.get('name', 'guest')
        
        # handle user
        user = User.objects.filter(email=email).first()
        is_new_user = False
        if user:
            if not request_user or not request_user.is_authenticated or request_user.email != email:
                 raise ValidationError("user with this email already exists")
        else:
            user = User.objects.create(email=email, full_name=name, role='CLIENT', is_active=False)
            user.set_unusable_password()
            user.save()
            is_new_user = True

        # limit check
        pending_count = Booking.objects.filter(user=user, status__in=[Booking.Status.PENDING, Booking.Status.QUOTED]).count()
        if pending_count >= 2:
            raise ValidationError("you have reached the limit of 2 pending requests")

        # create booking
        booking = Booking.objects.create(
            user=user,
            departure_city=data.get('departure_city', ''),
            destination=data.get('destination', ''),
            arrival_date=data.get('arrival_date'),
            departure_date=data.get('departure_date'),
            adults=data.get('adults', 0),
            children=data.get('children', 0),
            infants=data.get('infants', 0),
            needs_flights=data.get('needs_flights', False),
            needs_hotel=data.get('needs_hotel', False),
            needs_car=data.get('needs_car', False),
            needs_guide=data.get('needs_guide', False),
            phone_number=data.get('phone_number', ''),
            trip_purpose=data.get('trip_purpose', ''),
            special_requests=data.get('special_requests', ''),
            status=Booking.Status.PENDING
        )
        
        # process items
        email_items = []
        for item in data.get('items', []):
            service = TripSubmissionService._resolve_service(item)
            unit_price = Decimal('0.00')
            qty = item.get('quantity', 1)
            
            booking_item = BookingItem.objects.create(
                booking=booking,
                user=user,
                service=service,
                item_type=item.get('type') or item.get('item_type') or 'service',
                title=service.title if service else item.get('title', 'service'),
                description=service.description if service else item.get('description', ''),
                start_date=item.get('start_date') or booking.arrival_date,
                end_date=item.get('end_date') or booking.departure_date,
                start_time=item.get('start_time'),
                end_time=item.get('end_time'),
                is_round_trip=item.get('is_round_trip', False),
                return_date=item.get('return_date'),
                return_time=item.get('return_time'),
                with_driver=item.get('with_driver', False),
                quantity=qty,
                unit_price=unit_price,
                subtotal=Decimal('0.00'),
                status=BookingItem.Status.RESERVED,
                metadata=item
            )
            
            email_items.append({
                'title': booking_item.title,
                'type': booking_item.item_type,
                'description': booking_item.description,
                'price': 0.0
            })

        TripSubmissionService._send_submission_notifications(user, booking, email_items, data, is_new_user)
        return booking
