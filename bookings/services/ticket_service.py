import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage

from bookings.models import Booking
from tickets.models import Ticket
from tickets.utils import generate_qr_code, generate_ticket_pdf

logger = logging.getLogger(__name__)

class TicketService:
    @staticmethod
    @transaction.atomic
    def generate_ticket(booking: Booking, request_user) -> Ticket:
        """Generate a ticket for a confirmed booking."""
        if booking.user != request_user and not request_user.is_staff:
            raise ValidationError("You do not have permission to generate a ticket for this booking.")
            
        if booking.status != 'confirmed':
            raise ValidationError("Tickets can only be generated for confirmed bookings.")

        # Check for successful payment
        if not hasattr(booking, 'payments') or not booking.payments.filter(status='succeeded').exists():
            raise ValidationError("No successful payment found for this booking.")

        payment = booking.payments.filter(status='succeeded').first()

        # Check if already exists
        if hasattr(booking, 'ticket'):
            return booking.ticket

        # Generate QR code data
        qr_data = f"VZT-{booking.id}-{payment.id}-{booking.user.id}"
        qr_code = generate_qr_code(qr_data)

        # Create ticket
        ticket = Ticket.objects.create(
            booking=booking,
            payment=payment,
            qr_code_data=qr_code,
            status='valid' # Assuming default is valid or similar
        )

        # Generate PDF
        try:
            pdf_path = generate_ticket_pdf(ticket)
            # In a real app, you'd want to store this properly
            # For now keeping it similar to existing logic
            ticket.pdf_url = f"/media/{pdf_path}"
            ticket.save()
        except Exception as e:
            logger.error(f"Failed to generate ticket PDF for ticket {ticket.id}: {e}")
            # We might want to keep the ticket even if PDF fails? 
            # Or raise if PDF is critical.
            
        return ticket

    @staticmethod
    def verify_ticket(qr_data: str) -> dict:
        """Verify a ticket from QR data."""
        if not qr_data:
            raise ValidationError("QR code data required.")

        try:
            ticket = Ticket.objects.select_related('booking', 'booking__user').get(qr_code_data=qr_data)
        except Ticket.DoesNotExist:
            return {'valid': False, 'message': 'Invalid ticket'}

        # Check expiry
        if ticket.expires_at < timezone.now():
            return {'valid': False, 'message': 'Ticket has expired'}

        # Check booking status
        if ticket.booking.status != 'confirmed':
            return {'valid': False, 'message': 'Booking not confirmed'}

        return {
            'valid': True,
            'ticket_id': str(ticket.id),
            'booking_id': str(ticket.booking.id),
            'user': ticket.booking.user.full_name or ticket.booking.user.email,
            'total_amount': float(ticket.booking.total_amount),
            'currency': ticket.booking.currency,
            'issued_at': ticket.issued_at.isoformat(),
            'expires_at': ticket.expires_at.isoformat()
        }

    @staticmethod
    def get_ticket_file(booking: Booking, request_user):
        """Get the PDF content and filename for a ticket."""
        if booking.user != request_user and not request_user.is_staff:
             raise ValidationError("Permission denied.")

        if not hasattr(booking, 'ticket'):
             raise ValidationError("No ticket found for this booking.")

        ticket = booking.ticket
        if not ticket.pdf_url:
             raise ValidationError("Ticket PDF not generated yet.")

        try:
            pdf_path = ticket.pdf_url.split('/media/')[-1]
        except (IndexError, AttributeError):
             raise ValidationError("Invalid ticket URL.")

        if not default_storage.exists(pdf_path):
             raise ValidationError("Ticket file not found.")

        try:
            file_content = default_storage.open(pdf_path).read()
            filename = f"ticket_{booking.id}.pdf"
            return file_content, filename
        except Exception as e:
             logger.error(f"Failed to read ticket file for booking {booking.id}: {e}")
             raise ValidationError("Failed to read ticket file.")
