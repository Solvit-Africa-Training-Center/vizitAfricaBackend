import logging
import threading
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class EmailThread(threading.Thread):
    def __init__(self, subject, text_content, html_content, from_email, recipient_list):
        self.subject = subject
        self.text_content = text_content
        self.html_content = html_content
        self.from_email = from_email
        self.recipient_list = recipient_list
        threading.Thread.__init__(self)

    def run(self):
        try:
            msg = EmailMultiAlternatives(
                self.subject, 
                self.text_content, 
                self.from_email, 
                self.recipient_list
            )
            if self.html_content:
                msg.attach_alternative(self.html_content, "text/html")
            msg.send()
        except Exception as e:
            logger.error(f"Failed to send email to {self.recipient_list}: {e}")

def _send_async_email(subject, context, template_name, recipient_email):
    """
    Internal helper to render template and send email asynchronously.
    """
    from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@vizit-africa.com'
    recipient_list = [recipient_email]

    try:
        html_content = render_to_string(template_name, context)
    except Exception as e:
        logger.error(f"Template rendering failed for {template_name}: {e}")
        return 0

    text_content = "Please enable HTML to view this email."

    EmailThread(subject, text_content, html_content, from_email, recipient_list).start()
    return 1 

def send_verification_email(recipient_email, code):
    """Send an email containing a verification link (token)."""
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    verification_link = (
        f"{frontend_url}/en/verify-email?"
        f"email={quote_plus(str(recipient_email))}&token={quote_plus(str(code))}"
    )

    context = {
        'code': code,
        'verification_link': verification_link
    }
    
    return _send_async_email(
        subject="Verify Your Vizit Africa Account",
        context=context,
        template_name="emails/verify_email.html",
        recipient_email=recipient_email
    )

def send_itinerary_email(recipient_email, guest_name, items, password_link):
    """Send an email with the trip itinerary and a link to set account password."""
    context = {
        'guest_name': guest_name,
        'items': items,
        'password_link': password_link
    }

    return _send_async_email(
        subject="Your Vizit Africa Itinerary Draft",
        context=context,
        template_name="emails/itinerary.html",
        recipient_email=recipient_email
    )

def send_admin_trip_notification(guest_name, guest_email, booking_id, items, trip_dates):
    """Send an email to admin notifying them of a new trip request."""
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@vizit-africa.com')
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    
    # Calculate total estimate for the email
    total_estimate = sum(item.get('price', 0) for item in items)

    context = {
        'guest_name': guest_name,
        'guest_email': guest_email,
        'booking_id': booking_id,
        'items': items,
        'trip_dates': trip_dates,
        'total_estimate': total_estimate,
        'admin_dashboard_link': f"{frontend_url}/en/admin/requests"
    }

    return _send_async_email(
        subject=f"New Trip Request from {guest_name}",
        context=context,
        template_name="emails/admin_notification.html",
        recipient_email=admin_email
    )


def send_client_quote_email(recipient_email, guest_name, booking_id, quote_items, total_amount, currency="USD"):
    """Send an email to client with the generated quote."""
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

    context = {
        'guest_name': guest_name,
        'booking_id': booking_id,
        'items': quote_items,
        'total_amount': total_amount,
        'currency': currency,
        'dashboard_link': f"{frontend_url}/en/profile"
    }

    return _send_async_email(
        subject=f"Your Vizit Africa Quote #{booking_id}",
        context=context,
        template_name="emails/client_quote.html",
        recipient_email=recipient_email
    )

def send_vendor_booking_request(booking):
    """
    Send email to vendors for a confirmed booking.
    Groups items by vendor (service owner) and sends individual emails.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    
    # 1. Group items by vendor
    vendor_items = {}
    items = booking.items.all().select_related('service', 'service__user')
    
    for item in items:
        if not item.service or not item.service.user:
            continue
            
        vendor = item.service.user
        if vendor not in vendor_items:
            vendor_items[vendor] = []
        vendor_items[vendor].append(item)
    
    # 2. Send email to each vendor
    for vendor, v_items in vendor_items.items():
        context = {
            'vendor_name': vendor.full_name or "Partner",
            'guest_name': booking.user.full_name,
            'booking_id': str(booking.id),
            'items': [
                {
                    'title': item.service.title,
                    'start_date': item.start_date,
                    'start_time': item.start_time,
                    'quantity': item.quantity,
                    'notes': item.metadata.get('notes', '')
                }
                for item in v_items
            ],
            'dashboard_link': f"{frontend_url}/en/vendor/bookings"
        }
        
        try:
            _send_async_email(
                subject=f"New Booking Request #{booking.id}",
                context=context,
                template_name="emails/vendor_booking_request.html",
                recipient_email=vendor.email
            )
        except Exception as e:
            print(f"Failed to send email to vendor {vendor.email}: {e}")

def send_vendor_inquiry_email(recipient_email, vendor_name, item_details):
    """
    Send an email to a vendor inquiring about availability for a specific service.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

    context = {
        'vendor_name': vendor_name or "Partner",
        'service_title': item_details.get('title', 'Service'),
        'service_type': item_details.get('type', 'Service'),
        'date': item_details.get('date', 'N/A'),
        'quantity': item_details.get('quantity', 1),
        'notes': item_details.get('description', ''),
        # In a real app, this might link to a vendor dashboard to reply directly
        'dashboard_link': f"{frontend_url}/en/vendor/inquiries"
    }

    return _send_async_email(
        subject=f"Availability Inquiry: {item_details.get('title', 'Service')}",
        context=context,
        template_name="emails/vendor_inquiry.html",
        recipient_email=recipient_email
    )

