from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from .models import BookingItem, Booking, Package, PackageItem
from accounts.models import User
from .serializers import (
    BookingItemSerializer, BookingSerializer, TripSubmissionSerializer,
    AdminBookingSerializer, PackageSerializer, PackageItemSerializer
)
from .services import FinancialService
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


from bookings.services.booking_service import BookingService, TripSubmissionService
from bookings.services.ticket_service import TicketService
from bookings.services import FinancialService, QuoteService
from accounts.permissions import IsAdmin
from .serializers import AdminBookingSerializer

# ===================================================
# BOOKING ITEM VIEWS
# ===================================================
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

# ===================================================
# BOOKING VIEWS
# ===================================================
class ConfirmBookingView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        # Service handles atomic transaction and business logic
        booking = BookingService.create_from_drafts(request.user)
        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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

class TripSubmissionView(generics.CreateAPIView):
    """
    POST /api/bookings/submit/
    Handles guest trip form submissions.
    """
    serializer_class = BookingSerializer 
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        submission_serializer = TripSubmissionSerializer(data=request.data)
        submission_serializer.is_valid(raise_exception=True)
        
        # Service handles complex multi-step logic
        booking = TripSubmissionService.process_submission(
            data=submission_serializer.validated_data,
            request_user=request.user
        )
        
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

# ===================================================
# TICKET VIEWS
# ===================================================
@api_view(['POST'])
def generate_ticket(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    ticket = TicketService.generate_ticket(booking, request.user)
    serializer = TicketSerializer(ticket)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def download_ticket(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    file_content, filename = TicketService.get_ticket_file(booking, request.user)
    
    response = HttpResponse(file_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@api_view(['POST'])
def verify_ticket(request):
    qr_data = request.data.get('qr_code_data')
    result = TicketService.verify_ticket(qr_data)
    return Response(result, status=status.HTTP_200_OK)

# ===================================================
# FINANCIAL VIEWS
# ===================================================
@api_view(['POST'])
def process_commission(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    transaction = FinancialService.process_commission(booking)
    
    if not transaction:
         return Response({'message': 'Commission already processed'}, status=status.HTTP_200_OK)

    serializer = TransactionSerializer(transaction)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user)
    transaction_type = request.query_params.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def process_payout(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    transaction = FinancialService.process_payout(booking)
    
    if not transaction:
         return Response({'message': 'Payout already processed'}, status=status.HTTP_200_OK)

    serializer = TransactionSerializer(transaction)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def vendor_payouts(request):
    payouts = Transaction.objects.filter(user=request.user, transaction_type='payout')
    status_filter = request.query_params.get('status')
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    
    serializer = TransactionSerializer(payouts, many=True)
    return Response(serializer.data)

# ===================================================
# ADMIN BOOKING VIEWS
# ===================================================
class AdminBookingListView(generics.ListAPIView):
    queryset = Booking.objects.all().order_by('-created_at')
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

class AdminBookingDetailView(generics.RetrieveAPIView):
    queryset = Booking.objects.all()
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

# ===================================================
# PACKAGE VIEWS
# ===================================================
class PackageViewSet(viewsets.ModelViewSet):
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
        serializer.is_valid(raise_exception=True)
        serializer.save(package=package)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class PackageItemViewSet(viewsets.ModelViewSet):
    queryset = PackageItem.objects.all()
    serializer_class = PackageItemSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

# ===================================================
# QUOTE & ACTION VIEWS
# ===================================================
@api_view(['POST'])
def send_quote(request, booking_id):
    if not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        return Response({'error': 'Only admin can send quotes'}, status=status.HTTP_403_FORBIDDEN)

    booking = generics.get_object_or_404(Booking, id=booking_id)
    items = request.data.get('items')
    if not items or not isinstance(items, list):
         return Response({'error': 'Items list is required'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Generate Quote
    updated_booking = QuoteService.generate_quote(booking, items, request.user)
    
    # 2. Send Email
    try:
         from accounts.utils.send_email import send_client_quote_email
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
        logger.error(f"Email sending failed for booking {booking.id}: {e}")
        
    return Response({
        'message': 'Quote sent successfully',
        'booking_id': str(updated_booking.id),
        'total_amount': updated_booking.total_amount,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def accept_quote(request, booking_id):
    from django.core.exceptions import ValidationError
    booking = generics.get_object_or_404(Booking, id=booking_id, user=request.user)
    try:
        confirmed_booking = BookingService.confirm_quote(booking)
    except ValidationError as e:
        return Response({'error': str(e.message)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'message': 'Quote accepted and booking confirmed',
        'booking_id': str(confirmed_booking.id),
        'status': confirmed_booking.status,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def cancel_booking(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    BookingService.cancel_booking(booking, request.user)
    return Response({'message': 'Booking cancelled successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
def notify_vendor(request, booking_id):
    """
    Notify a vendor about a specific item in a booking to check availability.
    """
    if not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        return Response({'error': 'Only admin can notify vendors'}, status=status.HTTP_403_FORBIDDEN)

    item_id = request.data.get('item_id')
    service_id = request.data.get('service_id')

    if not item_id and not service_id:
        return Response({'error': 'Item ID or Service ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    from services.models import Service
    service = None
    
    if item_id:
        booking_item = BookingItem.objects.filter(id=item_id).first()
        if booking_item: service = booking_item.service
    
    if not service and service_id:
        service = Service.objects.filter(id=service_id).first() or Service.objects.filter(external_id=service_id).first()

    if not service:
        return Response({'error': 'Service not found to notify vendor'}, status=status.HTTP_404_NOT_FOUND)

    vendor = service.user
    if not vendor or not vendor.email:
         return Response({'error': 'Vendor not found or has no email'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.utils.send_email import send_vendor_inquiry_email
    
    dates = request.data.get('date', 'Specified Dates')
    times = "Not specified"
    metadata = {}
    requirements = ""

    if booking_item:
        dates = f"{booking_item.start_date} - {booking_item.end_date}"
        times = f"Start: {booking_item.start_time or 'N/A'}, End: {booking_item.end_time or 'N/A'}"
        if booking_item.is_round_trip:
            times += f", Return: {booking_item.return_date or 'N/A'} at {booking_item.return_time or 'N/A'}"
        metadata = booking_item.metadata
        requirements = booking_item.description

    details = {
        'item_id': str(item_id) if item_id else None,
        'service_title': service.title,
        'dates': dates,
        'times': times,
        'quantity': request.data.get('quantity', 1),
        'requirements': requirements,
        'metadata': metadata
    }
    
    send_vendor_inquiry_email(vendor.email, vendor.full_name, details)
    return Response({'message': f'Inquiry sent to {vendor.email}'}, status=status.HTTP_200_OK)


