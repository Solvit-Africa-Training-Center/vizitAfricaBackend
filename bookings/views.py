from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.http import HttpResponse, Http404
from django.utils import timezone
from decimal import Decimal
import uuid

from .models import BookingItem, Booking, Package, PackageItem
from accounts.models import User
from .serializers import (
    BookingItemSerializer, BookingSerializer, TripSubmissionSerializer,
    AdminBookingSerializer, PackageSerializer, PackageItemSerializer
)
from .services.booking_service import BookingService, TripSubmissionService
from .services.ticket_service import TicketService
from .services import FinancialService, QuoteService
from accounts.permissions import IsAdmin
from tickets.models import Ticket
from tickets.serializers import TicketSerializer

# booking item views
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

# booking views
class ConfirmBookingView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
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
    # handle trip requests
    serializer_class = BookingSerializer 
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        submission_serializer = TripSubmissionSerializer(data=request.data)
        submission_serializer.is_valid(raise_exception=True)
        
        booking = TripSubmissionService.process_submission(
            data=submission_serializer.validated_data,
            request_user=request.user
        )
        
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

# ticket views
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

# financial views
@api_view(['POST'])
def process_commission(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    transaction = FinancialService.process_commission(booking)
    
    if not transaction:
         return Response({'message': 'commission already processed'}, status=status.HTTP_200_OK)

    from transactions.serializers import TransactionSerializer
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def transaction_history(request):
    from transactions.models import Transaction
    from transactions.serializers import TransactionSerializer
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
         return Response({'message': 'payout already processed'}, status=status.HTTP_200_OK)

    from transactions.serializers import TransactionSerializer
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def vendor_payouts(request):
    from transactions.models import Transaction
    from transactions.serializers import TransactionSerializer
    payouts = Transaction.objects.filter(user=request.user, transaction_type='payout')
    status_filter = request.query_params.get('status')
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    
    serializer = TransactionSerializer(payouts, many=True)
    return Response(serializer.data)

# admin booking views
class AdminBookingListView(generics.ListAPIView):
    queryset = Booking.objects.all().order_by('-created_at')
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

class AdminBookingDetailView(generics.RetrieveAPIView):
    queryset = Booking.objects.all()
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

# package views
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

# quote actions
@api_view(['POST'])
def send_quote(request, booking_id):
    if not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        return Response({'error': 'only admin can send quotes'}, status=status.HTTP_403_FORBIDDEN)

    booking = generics.get_object_or_404(Booking, id=booking_id)
    items = request.data.get('items')
    if not items or not isinstance(items, list):
         return Response({'error': 'items list is required'}, status=status.HTTP_400_BAD_REQUEST)

    # generate quote
    updated_booking = QuoteService.generate_quote(booking, items, request.user)
    
    # send email
    try:
         from accounts.utils.send_email import send_client_quote_email
         email_items = [
             {
                 'title': item.title,
                 'quantity': item.quantity,
                 'unit_price': float(item.unit_price),
                 'line_total': float(item.subtotal)
             }
             for item in updated_booking.items.all()
         ]
         
         send_client_quote_email(
            recipient_email=updated_booking.user.email,
            guest_name=updated_booking.user.full_name,
            booking_id=updated_booking.id,
            quote_items=email_items,
            total_amount=float(updated_booking.total_amount),
            currency=updated_booking.currency,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"email sending failed: {e}")
        
    return Response({
        'message': 'quote sent successfully',
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
        'message': 'quote accepted',
        'booking_id': str(confirmed_booking.id),
        'status': confirmed_booking.status,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def cancel_booking(request, booking_id):
    booking = generics.get_object_or_404(Booking, id=booking_id)
    BookingService.cancel_booking(booking, request.user)
    return Response({'message': 'booking cancelled successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
def notify_vendor(request, booking_id):
    # notify vendor for availability
    if not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        return Response({'error': 'only admin can notify vendors'}, status=status.HTTP_403_FORBIDDEN)

    item_id = request.data.get('item_id')
    service_id = request.data.get('service_id')

    if not item_id and not service_id:
        return Response({'error': 'item_id or service_id required'}, status=status.HTTP_400_BAD_REQUEST)

    from services.models import Service
    service = None
    booking_item = None
    
    if item_id:
        booking_item = BookingItem.objects.filter(id=item_id).first()
        if booking_item: service = booking_item.service
    
    if not service and service_id:
        service = Service.objects.filter(id=service_id).first() or Service.objects.filter(external_id=service_id).first()

    if not service:
        return Response({'error': 'service not found'}, status=status.HTTP_404_NOT_FOUND)

    vendor = service.user
    if not vendor or not vendor.email:
         return Response({'error': 'vendor not found'}, status=status.HTTP_404_NOT_FOUND)

    from accounts.utils.send_email import send_vendor_inquiry_email
    
    dates = f"{booking_item.start_date} - {booking_item.end_date}" if booking_item else "unspecified"
    times = f"start: {booking_item.start_time or 'n/a'}" if booking_item else "unspecified"

    details = {
        'item_id': str(item_id) if item_id else None,
        'service_title': service.title,
        'dates': dates,
        'times': times,
        'quantity': request.data.get('quantity', 1),
        'requirements': booking_item.description if booking_item else "",
        'metadata': booking_item.metadata if booking_item else {}
    }
    
    send_vendor_inquiry_email(vendor.email, vendor.full_name, details)
    return Response({'message': f'inquiry sent to {vendor.email}'}, status=status.HTTP_200_OK)
