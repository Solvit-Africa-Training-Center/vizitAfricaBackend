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
        user = request.user if request.user.is_authenticated else None
        
        if not user:
            email = data.get('email')
            if not email:
                return Response({'error': 'Email is required for guest checkout'}, status=status.HTTP_400_BAD_REQUEST)
            
            from accounts.models import User
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': data.get('name', 'Guest User'),
                    'role': 'CLIENT',
                    'is_active': True 
                }
            )
            # Update name if it's different and user was already there
            if not created:
                if data.get('name') and user.full_name != data.get('name'):
                    user.full_name = data.get('name')
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
        
        # 4. Process Items
        from services.models import Service
        
        for item in items_data:
            # Skip notes/unknown types for now, or handle them
            if item.get('type') == 'note':
                continue
                
            # Resolve service using external_id aliases and title fallback.
            service = _resolve_service(item, Service)
            
            if not service:
               
                
                
                if item.get('type') == 'flight':
                    
                    pass # Logic to handle missing flights if dynamic
                
                if not service:
                     
                     
                     if item.get('type') == 'flight':
                         
                         continue 

            
            
            unit_price = service.base_price if service else Decimal(str(item.get('price', 0)))
            quantity = item.get('quantity', 1)
            
            # Dates
            start_date = data['departureDate']
            end_date = data.get('returnDate') or start_date
            
            # Create Item
            if service:
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

        # 5. Update Total
        booking.total_amount = total
        booking.save()
        # 6. Send Itinerary Email & Password Link
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
            
            # Use the local/frontend URL for the password set page
            # Assuming the frontend has a page to handle these params
            password_link = f"http://localhost:3000/en/set-password?uidb64={uid}&token={token}"
            
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

        # 7. Return Response
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
            'user': ticket.booking.user.get_full_name() or ticket.booking.user.username,
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

    items = request.data.get('items') or []
    if not isinstance(items, list) or len(items) == 0:
        return Response({'error': 'Quote items are required'}, status=status.HTTP_400_BAD_REQUEST)

    currency = request.data.get('currency') or booking.currency or 'USD'
    notes = request.data.get('notes', '')
    expires_at = request.data.get('expires_at')

    normalized_items = []
    grand_total = Decimal('0.00')

    for item in items:
        title = item.get('title') or 'Service'
        item_type = item.get('type') or 'service'
        quantity = int(item.get('quantity') or 1)
        unit_price = Decimal(str(item.get('unit_price') or 0))
        line_total = unit_price * quantity
        grand_total += line_total

        normalized_items.append({
            'id': item.get('id'),
            'service': item.get('service'),
            'type': item_type,
            'title': title,
            'description': item.get('description', ''),
            'quantity': quantity,
            'unit_price': float(unit_price),
            'line_total': float(line_total),
        })

    guest_info = dict(booking.guest_info or {})
    guest_info['packageQuote'] = {
        'status': 'quoted',
        'sent_at': timezone.now().isoformat(),
        'sent_by': str(request.user.id),
        'currency': currency,
        'total_amount': float(grand_total),
        'notes': notes,
        'expires_at': expires_at,
        'items': normalized_items,
    }
    booking.guest_info = guest_info
    booking.total_amount = grand_total
    booking.status = 'quoted'
    booking.save(update_fields=['guest_info', 'total_amount', 'status', 'updated_at'])

    recipient_email = guest_info.get('email') or booking.user.email
    recipient_name = guest_info.get('name') or booking.user.full_name

    try:
        send_client_quote_email(
            recipient_email=recipient_email,
            guest_name=recipient_name,
            booking_id=booking.id,
            quote_items=normalized_items,
            total_amount=float(grand_total),
            currency=currency,
        )
    except Exception:
        # Quote persistence must succeed even if email transport fails.
        pass

    return Response({
        'message': 'Quote sent successfully',
        'booking_id': str(booking.id),
        'total_amount': float(grand_total),
        'currency': currency,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def accept_quote(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    guest_info = dict(booking.guest_info or {})
    quote = guest_info.get('packageQuote')
    if not isinstance(quote, dict):
        return Response({'error': 'No quote found for this booking'}, status=status.HTTP_400_BAD_REQUEST)

    quote_status = str(quote.get('status', '')).lower()
    if quote_status not in ['quoted', 'sent']:
        return Response({'error': 'This quote is not available for acceptance'}, status=status.HTTP_400_BAD_REQUEST)

    quote['status'] = 'accepted'
    quote['accepted_at'] = timezone.now().isoformat()
    quote['accepted_by'] = str(request.user.id)
    guest_info['packageQuote'] = quote

    quote_total = quote.get('total_amount')
    if quote_total is not None:
        booking.total_amount = Decimal(str(quote_total))

    booking.guest_info = guest_info
    booking.status = 'confirmed'
    booking.save(update_fields=['guest_info', 'status', 'total_amount', 'updated_at'])

    # If no booking items exist, try to materialize quoted services into BookingItem rows.
    if not booking.items.exists():
        from services.models import Service

        start_date_raw = guest_info.get('departureDate')
        end_date_raw = guest_info.get('returnDate') or start_date_raw
        try:
            start_date = date.fromisoformat(start_date_raw) if start_date_raw else timezone.now().date()
        except Exception:
            start_date = timezone.now().date()
        try:
            end_date = date.fromisoformat(end_date_raw) if end_date_raw else start_date
        except Exception:
            end_date = start_date

        for quote_item in quote.get('items', []):
            service = None
            service_ref = quote_item.get('service') or quote_item.get('id')
            if service_ref:
                service = Service.objects.filter(external_id=str(service_ref)).first()
            if not service and quote_item.get('title'):
                service = Service.objects.filter(title__iexact=quote_item.get('title')).first()
            if not service:
                continue

            quantity = int(quote_item.get('quantity') or 1)
            unit_price = Decimal(str(quote_item.get('unit_price') or service.base_price or 0))
            BookingItem.objects.create(
                booking=booking,
                service=service,
                user=request.user,
                start_date=start_date,
                end_date=end_date,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=unit_price * quantity,
                status='booked',
            )

    return Response({
        'message': 'Quote accepted successfully',
        'booking_id': str(booking.id),
        'status': booking.status,
    }, status=status.HTTP_200_OK)
