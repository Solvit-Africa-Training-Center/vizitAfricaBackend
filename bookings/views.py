from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from .models import BookingItem, Booking, Package, PackageItem
from .serializers import (
    BookingItemSerializer, BookingSerializer, TripSubmissionSerializer,
    AdminBookingSerializer, PackageSerializer, PackageItemSerializer
)
# Tickets related imports
from rest_framework.decorators import api_view
from tickets.models import Ticket
from accounts.utils.send_email import (
    send_itinerary_email,
    send_admin_trip_notification,
    send_client_quote_email,
)
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from tickets.serializers import TicketSerializer
from tickets.utils import generate_qr_code, generate_ticket_pdf
from django.http import HttpResponse, Http404
from django.core.files.storage import default_storage
import os
from django.utils import timezone
#Transactions import
from transactions.models import Transaction
from transactions.serializers import TransactionSerializer
from decimal import Decimal
from datetime import date


def _candidate_external_ids(raw_id, item_type):
    if not raw_id:
        return []

    raw = str(raw_id).strip()
    item_type = str(item_type or "").lower()
    candidates = [raw]

    if raw.startswith(("fl-", "ht-", "car-", "gd-")):
        return candidates

    if item_type == "flight" and raw.startswith("f"):
        suffix = raw[1:]
        if suffix.isdigit():
            candidates.append(f"fl-{suffix}")
    elif item_type in ["hotel", "accommodation"] and raw.startswith("h"):
        suffix = raw[1:]
        if suffix.isdigit():
            candidates.append(f"ht-{suffix}")
    elif item_type in ["car", "car_rental", "transport"] and raw.startswith("c"):
        suffix = raw[1:]
        if suffix.isdigit():
            candidates.append(f"car-{suffix}")
    elif item_type in ["guide", "experience", "tour"] and raw.startswith("g"):
        suffix = raw[1:]
        if suffix.isdigit():
            candidates.append(f"gd-{suffix}")

    return candidates


def _resolve_service(item, Service):
    external_id = item.get('service') or item.get('id')
    item_type = item.get('type')

    candidate_ids = _candidate_external_ids(external_id, item_type)
    service = Service.objects.filter(external_id__in=candidate_ids).first()
    if service:
        return service

    title = (item.get('title') or "").strip()
    if title:
        return Service.objects.filter(title__iexact=title).first()

    return None



class CreateBookingItemView(generics.CreateAPIView):
    serializer_class = BookingItemSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UpdateBookingItemView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BookingItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BookingItem.objects.filter(user=self.request.user, status='draft')

class BookingItemListView(generics.ListAPIView):
    serializer_class = BookingItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BookingItem.objects.filter(user=self.request.user, status='draft')

class ConfirmBookingView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            draft_items = BookingItem.objects.filter(user=request.user, status='draft')
            
            if not draft_items.exists():
                return Response(
                    {'error': 'No draft booking items found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create booking
            booking = Booking.objects.create(
                user=request.user,
                total_amount=sum(item.subtotal for item in draft_items),
                currency='USD'
            )
            
            # Update items
            draft_items.update(booking=booking, status='reserved')
            
            serializer = self.get_serializer(booking)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': 'Failed to create booking'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)

class BookingDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)
    


@api_view(['POST'])
def generate_ticket(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user, status='confirmed')
        
        # Check if booking has payment
        if not hasattr(booking, 'payments') or not booking.payments.filter(status='succeeded').exists():
            return Response({'error': 'No successful payment found'}, status=status.HTTP_400_BAD_REQUEST)
        
        payment = booking.payments.filter(status='succeeded').first()
        
        # Check if ticket already exists
        if hasattr(booking, 'ticket'):
            serializer = TicketSerializer(booking.ticket)
            return Response(serializer.data)
        
        # Generate QR code data
        qr_data = f"VZT-{booking.id}-{payment.id}-{booking.user.id}"
        qr_code = generate_qr_code(qr_data)
        
        # Create ticket
        ticket = Ticket.objects.create(
            booking=booking,
            payment=payment,
            qr_code_data=qr_code
        )
        
        # Generate PDF
        pdf_path = generate_ticket_pdf(ticket)
        ticket.pdf_url = request.build_absolute_uri(f"/media/{pdf_path}")
        ticket.save()
        
        serializer = TicketSerializer(ticket)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)



@api_view(['GET'])
def download_ticket(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        
        if not hasattr(booking, 'ticket'):
            return Response({'error': 'No ticket found for this booking'}, status=status.HTTP_404_NOT_FOUND)
        
        ticket = booking.ticket
        if not ticket.pdf_url:
            return Response({'error': 'Ticket PDF not generated yet'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract file path from URL safely
        try:
            pdf_path = ticket.pdf_url.split('/media/')[-1]
        except (IndexError, AttributeError):
            return Response({'error': 'Invalid ticket URL'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not default_storage.exists(pdf_path):
            return Response({'error': 'Ticket file not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Serve the file
        try:
            file_content = default_storage.open(pdf_path).read()
            response = HttpResponse(file_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ticket_{booking.id}.pdf"'
            return response
        except Exception:
            return Response({'error': 'Failed to read ticket file'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TripSubmissionView(generics.CreateAPIView):
    
    serializer_class = BookingSerializer # Response serializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # 1. Validate Payload
        submission_serializer = TripSubmissionSerializer(data=request.data)
        submission_serializer.is_valid(raise_exception=True)
        data = submission_serializer.validated_data
        
        # 2. Extract Data
        import datetime
        guest_info = {}
        for k, v in data.items():
            if k == 'items':
                continue
            if isinstance(v, (datetime.date, datetime.datetime)):
                guest_info[k] = v.isoformat()
            else:
                guest_info[k] = v
        
        items_data = data['items']

        # Keep the original requested items so admins can build packages even
        # when an item does not map to a Service.external_id yet.
        guest_info['requestedItems'] = [
            {
                'id': item.get('id') or item.get('service'),
                'service': item.get('service') or item.get('id'),
                'type': item.get('type', 'service'),
                'category': item.get('category', ''),
                'title': item.get('title', 'Service'),
                'description': item.get('description', ''),
                'price': item.get('price', 0),
                'quantity': item.get('quantity', 1),
            }
            for item in items_data
            if item.get('type') != 'note'
        ]
        
        # 3. Handle User (Authenticated or Guest)
        email = data.get('email')
        if not email:
             return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Security: If user exists, requester MUST be that user
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if not request.user.is_authenticated or request.user.email != email:
                 return Response(
                     {"error": "User with this email already exists. Please login to continue."}, 
                     status=status.HTTP_403_FORBIDDEN
                 )
            user = existing_user
            
            # Update name if provided and allowed? 
            # For now let's not auto-update established profiles from a guest form.
        else:
            # Create new GUEST/INACTIVE user
            user = User.objects.create(
                email=email,
                full_name=data.get('name', 'Guest'),
                role='CLIENT',
                is_active=False  # Must verify email first
            )
            user.set_unusable_password()
            user.save()

        # 4. Create Booking
        booking = Booking.objects.create(
            user=user,
            total_amount=Decimal('0.00'), # Will calculate below
            currency='USD',
            status='pending',
            guest_info=guest_info
        )
        
        total = Decimal('0.00')
        
        # 5. Process Items
        from services.models import Service
        
        for item in items_data:
            # Skip notes/unknown types for now, or handle them
            if item.get('type') == 'note':
                continue
                
            # Resolve service using external_id aliases and title fallback.
            service = _resolve_service(item, Service)
            
            unit_price = service.base_price if service else Decimal(str(item.get('price', 0)))
            quantity = item.get('quantity', 1)
            
            # Dates
            start_date = data.get('departureDate')
            end_date = data.get('returnDate') or start_date
            
            # Create Item
            booking_item = BookingItem.objects.create(
                booking=booking,
                service=service,
                user=user,
                start_date=start_date,
                end_date=end_date,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=unit_price * quantity,
                status='reserved'
            )
            total += booking_item.subtotal

        # 6. Update Total
        booking.total_amount = total
        booking.save()

        # 7. Send Itinerary Email & Password Link
        try:
            # Prepare items for email summary
            email_items = []
            for item in items_data:
                # Get service name if possible
                svc = _resolve_service(item, Service)
                email_items.append({
                    'title': svc.title if svc else item.get('title', 'Service'),
                    'type': item.get('type', 'experience'),
                    'description': svc.description if svc else item.get('description', ''),
                    'price': item.get('price', 0)
                })
            
            # Generate Password Link
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            # Use configured frontend URL
            from django.conf import settings
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            password_link = f"{frontend_url}/en/set-password?uidb64={uid}&token={token}"
            
            send_itinerary_email(
                recipient_email=user.email,
                guest_name=user.full_name,
                items=email_items,
                password_link=password_link
            )
            
            # Send admin notification
            send_admin_trip_notification(
                guest_name=user.full_name,
                guest_email=user.email,
                booking_id=booking.id,
                items=email_items,
                trip_dates={
                    'arrival': data['departureDate'].isoformat() if data.get('departureDate') else 'N/A',
                    'departure': data.get('returnDate').isoformat() if data.get('returnDate') else 'N/A'
                }
            )
        except Exception as e:
            print(f"FAILED TO SEND EMAIL: {e}")

        # 8. Return Response
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def verify_ticket(request):
    qr_data = request.data.get('qr_code_data')
    
    if not qr_data:
        return Response({'error': 'QR code data required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ticket = Ticket.objects.get(qr_code_data=qr_data)
        
        # Check if ticket is expired
        from django.utils import timezone
        if ticket.expires_at < timezone.now():
            return Response({
                'valid': False,
                'message': 'Ticket has expired'
            }, status=status.HTTP_200_OK)
        
        # Check booking status
        if ticket.booking.status != 'confirmed':
            return Response({
                'valid': False,
                'message': 'Booking not confirmed'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'valid': True,
            'ticket_id': ticket.id,
            'booking_id': ticket.booking.id,
            'user': ticket.booking.user.full_name or ticket.booking.user.email,
            'total_amount': ticket.booking.total_amount,
            'currency': ticket.booking.currency,
            'issued_at': ticket.issued_at,
            'expires_at': ticket.expires_at
        }, status=status.HTTP_200_OK)
        
    except Ticket.DoesNotExist:
        return Response({
            'valid': False,
            'message': 'Invalid ticket'
        }, status=status.HTTP_200_OK)




@api_view(['POST'])
def process_commission(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, status='confirmed')
        
        # Check if commission already processed
        if Transaction.objects.filter(booking=booking, transaction_type='commission').exists():
            return Response({'message': 'Commission already processed'}, status=status.HTTP_200_OK)
        
        # Calculate commission (10% of total amount)
        commission_rate = Decimal('0.10')
        commission_amount = booking.total_amount * commission_rate
        
        # Create commission transaction
        transaction = Transaction.objects.create(
            booking=booking,
            user=booking.user,
            amount=commission_amount,
            currency=booking.currency,
            transaction_type='commission',
            status='completed'
        )
        
        serializer = TransactionSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        return Response({'error': 'Failed to process commission'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user)
    
    # Filter by type if provided
    transaction_type = request.query_params.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def process_refund(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        
        if booking.status != 'confirmed':
            return Response({'error': 'Only confirmed bookings can be refunded'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already refunded
        if Transaction.objects.filter(booking=booking, transaction_type='refund').exists():
            return Response({'error': 'Booking already refunded'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create refund transaction
        transaction = Transaction.objects.create(
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
        
        serializer = TransactionSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['POST'])
def process_payout(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, status='confirmed')
        
        # Get the service owner (vendor) from booking items
        booking_items = booking.items.all()
        if not booking_items.exists():
            return Response({'error': 'No booking items found'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Assuming all items in a booking belong to the same vendor
        vendor = booking_items.first().service.user
        
        # Check if payout already processed
        if Transaction.objects.filter(booking=booking, transaction_type='payout').exists():
            return Response({'message': 'Payout already processed'}, status=status.HTTP_200_OK)
        
        # Calculate payout (90% of total amount - after 10% commission)
        commission_rate = Decimal('0.10')
        payout_amount = booking.total_amount * (Decimal('1.00') - commission_rate)
        
        # Create payout transaction
        transaction = Transaction.objects.create(
            booking=booking,
            user=vendor,  # Payout goes to vendor
            amount=payout_amount,
            currency=booking.currency,
            transaction_type='payout',
            status='completed'
        )
        
        serializer = TransactionSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def vendor_payouts(request):
    """Get all payouts for the current vendor"""
    payouts = Transaction.objects.filter(
        user=request.user, 
        transaction_type='payout'
    )
    
    # Filter by status if provided
    status_filter = request.query_params.get('status')
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    
    serializer = TransactionSerializer(payouts, many=True)
    return Response(serializer.data)

from accounts.permissions import IsAdmin
from .serializers import AdminBookingSerializer

class AdminBookingListView(generics.ListAPIView):
    """
    List all bookings for admin dashboard.
    """
    queryset = Booking.objects.all().order_by('-created_at')
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

class AdminBookingDetailView(generics.RetrieveAPIView):
    """
    Get detailed booking for admin.
    """
    queryset = Booking.objects.all()
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

class PackageViewSet(viewsets.ModelViewSet):
    """
    Manage custom packages for bookings.
    """
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        booking_id = self.request.query_params.get('booking_id')
        if booking_id:
            return self.queryset.filter(booking_id=booking_id)
        return self.queryset

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        package = self.get_object()
        serializer = PackageItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(package=package)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PackageItemViewSet(viewsets.ModelViewSet):
    queryset = PackageItem.objects.all()
    serializer_class = PackageItemSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


@api_view(['POST'])
def send_quote(request, booking_id):
    if not (request.user and request.user.is_authenticated and getattr(request.user, "role", "") == "ADMIN"):
        return Response({'error': 'Only admin can send quotes'}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    items = request.data.get('items')
    if not items or not isinstance(items, list):
         return Response({'error': 'Items list is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .services import QuoteService, NotificationService
        
        # 1. Generate Quote
        updated_booking = QuoteService.generate_quote(booking, items, request.user)
        
        # 2. Send Email
        try:
             # Re-using legacy email function for now, or move to NotificationService
             # Extract structured items for email template
             quote_data = updated_booking.guest_info.get('packageQuote')
             recipient_email = updated_booking.guest_info.get('email') or updated_booking.user.email
             recipient_name = updated_booking.guest_info.get('name') or updated_booking.user.full_name
             
             send_client_quote_email(
                recipient_email=recipient_email,
                guest_name=recipient_name,
                booking_id=updated_booking.id,
                quote_items=quote_data.get('items', []),
                total_amount=quote_data.get('total_amount'),
                currency=quote_data.get('currency'),
            )
        except Exception as e:
            print(f"Email sending failed: {e}")
            # Non-blocking
            
        return Response({
            'message': 'Quote sent successfully',
            'booking_id': str(updated_booking.id),
            'total_amount': updated_booking.total_amount,
            'currency': updated_booking.currency,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def accept_quote(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        from .services import BookingService
        
        # Confirm booking via service
        confirmed_booking = BookingService.confirm_booking(booking)
        
        return Response({
            'message': 'Quote accepted and booking confirmed',
            'booking_id': str(confirmed_booking.id),
            'status': confirmed_booking.status,
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f"Failed to confirm booking: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
