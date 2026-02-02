from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import BookingItem, Booking
from .serializers import BookingItemSerializer, BookingSerializer
# Tickets related imports
from rest_framework.decorators import api_view
from tickets.models import Ticket
from tickets.serializers import TicketSerializer
from tickets.utils import generate_qr_code, generate_ticket_pdf
from django.http import HttpResponse, Http404
from django.core.files.storage import default_storage
import os
from django.utils import timezone


class CreateBookingItemView(generics.CreateAPIView):
    serializer_class = BookingItemSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UpdateBookingItemView(generics.UpdateAPIView):
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

class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)

class BookingDetailView(generics.RetrieveAPIView):
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
        
        # Extract file path from URL
        pdf_path = ticket.pdf_url.split('/media/')[-1]
        
        if not default_storage.exists(pdf_path):
            return Response({'error': 'Ticket file not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Serve the file
        file_content = default_storage.open(pdf_path).read()
        response = HttpResponse(file_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ticket_{booking.id}.pdf"'
        
        return response
        
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


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
