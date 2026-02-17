from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from urllib.parse import quote_plus


def send_verification_email(recipient_email, code):
    """Send an email containing a verification link (token) instead of an OTP.

    Parameters:
    - recipient_email: recipient address
    - code: token string to include in the verification URL
    """
    subject = "Verify Your Vizit Africa Account"
    from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@vizit-africa.com'
    recipient_list = [recipient_email]

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    verification_link = (
        f"{frontend_url}/en/verify-email?"
        f"email={quote_plus(str(recipient_email))}&token={quote_plus(str(code))}"
    )

    text_content = (
        f"Verify your Vizit Africa account by visiting the link below:\n\n{verification_link}\n\n"
        f"Or enter this verification code: {code}\n\n"
        "If you did not request this, please ignore this email."
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8F9FA; color: #1A1A1A;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F8F9FA; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 4px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
                        <tr>
                            <td style="padding: 48px 40px; text-align: left;">
                                <div style="margin-bottom: 32px;">
                                    <span style="font-size: 20px; font-weight: 600; color: #2D4685; letter-spacing: -0.01em;">Vizit Africa</span>
                                </div>
                                <h1 style="color: #111827; margin: 0 0 16px 0; font-size: 28px; font-weight: 500; letter-spacing: -0.02em;">Verify your account</h1>
                                <p style="color: #4B5563; font-size: 16px; line-height: 1.6; margin: 0 0 32px 0;">
                                    Welcome to Vizit Africa. To complete your registration and start planning your journey, please verify your email address.
                                </p>
                                
                                <div style="background-color: #F9FAFB; border: 2px dashed #2D4685; border-radius: 8px; padding: 24px; margin: 32px 0; text-align: center;">
                                    <p style="color: #6B7280; font-size: 14px; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Your Verification Code</p>
                                    <div style="font-size: 36px; font-weight: 700; color: #2D4685; letter-spacing: 0.1em; font-family: 'Courier New', monospace; margin: 8px 0;">
                                        {code}
                                    </div>
                                    <p style="color: #9CA3AF; font-size: 12px; margin: 12px 0 0 0;">Enter this code on the verification page</p>
                                </div>
                                
                                <p style="color: #6B7280; font-size: 14px; line-height: 1.6; margin: 24px 0; text-align: center;">
                                    Or click the button below to verify automatically
                                </p>
                                
                                <div style="margin: 32px 0; text-align: center;">
                                    <a href="{verification_link}" style="background-color: #2D4685; color: #ffffff; text-decoration: none; padding: 16px 32px; border-radius: 4px; display: inline-block; font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Verify Email Address</a>
                                </div>
                                <p style="color: #6B7280; font-size: 14px; line-height: 1.6; margin: 32px 0 0 0; padding-top: 32px; border-top: 1px solid #F3F4F6;">
                                    If the button doesn't work, copy and paste this link into your browser:
                                    <br>
                                    <span style="word-break: break-all; color: #2D4685;">{verification_link}</span>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #F9FAFB; padding: 32px 40px; text-align: left;">
                                <p style="color: #9CA3AF; font-size: 12px; margin: 0; line-height: 1.5;">
                                    © 2024 Vizit Africa Logistics. All rights reserved.<br>
                                    Professional planning for unforgettable African experiences.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        return msg.send()
    except Exception as e:
        print(f"Email sending failed: {e}")
        return 0

def send_itinerary_email(recipient_email, guest_name, items, password_link):
    """Send an email with the trip itinerary and a link to set account password.

    Parameters:
    - recipient_email: Guest's email
    - guest_name: Guest's full name
    - items: List of trip items (dicts with 'title', 'type', 'description', 'price')
    - password_link: URL to set the password
    """
    subject = "Your Vizit Africa Itinerary Draft"
    from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@vizit-africa.com'
    recipient_list = [recipient_email]

    # Build items HTML
    items_html = ""
    for item in items:
        price_display = f"${item.get('price', 0)}" if item.get('price') else "Flexible"
        items_html += f"""
        <div style="padding: 24px 0; border-bottom: 1px solid #F3F4F6;">
            <div style="color: #2D4685; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px;">{item.get('type', 'SERVICE')}</div>
            <div style="color: #111827; font-size: 18px; font-weight: 500; margin-bottom: 4px;">{item.get('title', 'Trip Experience')}</div>
            <div style="color: #6B7280; font-size: 14px; margin-bottom: 12px; line-height: 1.5;">{item.get('description', '')}</div>
            <div style="color: #111827; font-size: 14px; font-weight: 600;">Est. Price: {price_display}</div>
        </div>
        """

    text_content = (
        f"Hello {guest_name},\n\n"
        "Thank you for planning your trip with Vizit Africa! We have received your request.\n\n"
        "Your Itinerary Summary:\n"
    )
    for item in items:
        text_content += f"- {item.get('title')} ({item.get('type')})\n"
    
    text_content += f"\nTo manage your booking and finalize your trip, please set your password using the link below:\n\n{password_link}\n\n"
    text_content += "Safe travels,\nThe Vizit Africa Team"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8F9FA; color: #1A1A1A;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F8F9FA; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 4px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
                        <tr>
                            <td style="padding: 48px 40px; text-align: left;">
                                <div style="margin-bottom: 32px;">
                                    <span style="font-size: 20px; font-weight: 600; color: #2D4685; letter-spacing: -0.01em;">Vizit Africa</span>
                                </div>
                                <h1 style="color: #111827; margin: 0 0 16px 0; font-size: 28px; font-weight: 500; letter-spacing: -0.02em;">Your Journey Plan</h1>
                                <p style="color: #4B5563; font-size: 16px; line-height: 1.6; margin: 0 0 32px 0;">
                                    Hello {guest_name}, we've received your trip request. Our specialists are now sourcing the best real-time options for your selected experiences.
                                </p>
                                
                                <div style="margin-bottom: 40px;">
                                    <div style="font-size: 14px; font-weight: 600; color: #111827; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #2D4685; padding-bottom: 8px; display: inline-block;">Proposed Itinerary</div>
                                    <div style="margin-top: 8px;">
                                        {items_html}
                                    </div>
                                </div>

                                <div style="background-color: #F9FAFB; border-radius: 4px; padding: 32px; text-align: center;">
                                    <h3 style="color: #111827; margin: 0 0 12px 0; font-size: 18px; font-weight: 500;">Complete your profile</h3>
                                    <p style="color: #4B5563; font-size: 14px; line-height: 1.6; margin: 0 0 24px 0;">
                                        Set your password now to track your request, view your finalized quote, and manage your travel documents in your dashboard.
                                    </p>
                                    <a href="{password_link}" style="background-color: #2D4685; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 4px; display: inline-block; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Set Account Password</a>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #F9FAFB; padding: 32px 40px; text-align: left;">
                                <p style="color: #9CA3AF; font-size: 12px; margin: 0; line-height: 1.5;">
                                    © 2024 Vizit Africa Logistics. All rights reserved.<br>
                                    Global standards, local expertise. 
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        return msg.send()
    except Exception as e:
        print(f"Itinerary email failed: {e}")
        return 0

def send_admin_trip_notification(guest_name, guest_email, booking_id, items, trip_dates):
    """Send an email to admin notifying them of a new trip request.

    Parameters:
    - guest_name: Guest's full name
    - guest_email: Guest's email address
    - booking_id: ID of the created booking
    - items: List of trip items (dicts with 'title', 'type', 'price')
    - trip_dates: Dict with 'arrival' and 'departure' dates
    """
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@vizit-africa.com')
    subject = f"New Trip Request from {guest_name}"
    from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@vizit-africa.com'
    recipient_list = [admin_email]

    # Build items HTML
    items_html = ""
    total_estimate = 0
    for item in items:
        price = item.get('price', 0)
        total_estimate += price
        price_display = f"${price}" if price else "TBD"
        items_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #E5E7EB;">
                <div style="font-weight: 600; color: #111827;">{item.get('title', 'Service')}</div>
                <div style="font-size: 12px; color: #6B7280; text-transform: uppercase;">{item.get('type', 'experience')}</div>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #E5E7EB; text-align: right; font-weight: 600; color: #2D4685;">{price_display}</td>
        </tr>
        """

    text_content = (
        f"New trip request received from {guest_name} ({guest_email}).\n\n"
        f"Booking ID: {booking_id}\n"
        f"Travel Dates: {trip_dates.get('arrival')} to {trip_dates.get('departure')}\n\n"
        "Please review this request in the admin dashboard."
    )

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    admin_dashboard_link = f"{frontend_url}/en/admin/requests"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8F9FA; color: #1A1A1A;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F8F9FA; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 4px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
                        <tr>
                            <td style="padding: 48px 40px; text-align: left;">
                                <div style="margin-bottom: 32px;">
                                    <span style="font-size: 20px; font-weight: 600; color: #2D4685; letter-spacing: -0.01em;">Vizit Africa Admin</span>
                                </div>
                                
                                <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                                    <div style="font-weight: 600; color: #92400E; margin-bottom: 4px;">🔔 New Trip Request</div>
                                    <div style="font-size: 14px; color: #78350F;">Action required: Review and quote</div>
                                </div>
                                
                                <h1 style="color: #111827; margin: 0 0 24px 0; font-size: 24px; font-weight: 500;">Trip Request #{booking_id}</h1>
                                
                                <div style="background-color: #F9FAFB; padding: 20px; border-radius: 4px; margin-bottom: 24px;">
                                    <table width="100%" cellpadding="0" cellspacing="0">
                                        <tr>
                                            <td style="padding: 8px 0; color: #6B7280; font-size: 14px;">Guest Name</td>
                                            <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{guest_name}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; color: #6B7280; font-size: 14px;">Email</td>
                                            <td style="padding: 8px 0; color: #2D4685; text-align: right;">{guest_email}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; color: #6B7280; font-size: 14px;">Arrival</td>
                                            <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{trip_dates.get('arrival', 'N/A')}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; color: #6B7280; font-size: 14px;">Departure</td>
                                            <td style="padding: 8px 0; color: #111827; font-weight: 600; text-align: right;">{trip_dates.get('departure', 'N/A')}</td>
                                        </tr>
                                    </table>
                                </div>
                                
                                <h2 style="color: #111827; margin: 32px 0 16px 0; font-size: 18px; font-weight: 600;">Requested Services</h2>
                                <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #E5E7EB; border-radius: 4px; overflow: hidden;">
                                    {items_html}
                                    <tr style="background-color: #F9FAFB;">
                                        <td style="padding: 16px; font-weight: 600; color: #111827;">Estimated Total</td>
                                        <td style="padding: 16px; text-align: right; font-weight: 700; color: #2D4685; font-size: 18px;">${total_estimate}</td>
                                    </tr>
                                </table>
                                
                                <div style="margin: 32px 0; text-align: center;">
                                    <a href="{admin_dashboard_link}" style="background-color: #2D4685; color: #ffffff; text-decoration: none; padding: 16px 32px; border-radius: 4px; display: inline-block; font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Review in Dashboard</a>
                                </div>
                                
                                <p style="color: #6B7280; font-size: 14px; line-height: 1.6; margin: 24px 0 0 0; padding-top: 24px; border-top: 1px solid #F3F4F6;">
                                    This is an automated notification. Please respond to the guest within 48 hours with a detailed quote.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #F9FAFB; padding: 32px 40px; text-align: left;">
                                <p style="color: #9CA3AF; font-size: 12px; margin: 0; line-height: 1.5;">
                                    © 2024 Vizit Africa Logistics. All rights reserved.<br>
                                    Admin notification system.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        return msg.send()
    except Exception as e:
        print(f"Admin notification email failed: {e}")
        return 0


def send_client_quote_email(recipient_email, guest_name, booking_id, quote_items, total_amount, currency="USD"):
    subject = f"Your Vizit Africa Quote #{booking_id}"
    from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@vizit-africa.com'
    recipient_list = [recipient_email]

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    dashboard_link = f"{frontend_url}/en/profile"

    rows_html = ""
    for item in quote_items:
        rows_html += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #E5E7EB;">{item.get('title', 'Service')}</td>
            <td style="padding:10px;border-bottom:1px solid #E5E7EB;text-align:center;">{item.get('quantity', 1)}</td>
            <td style="padding:10px;border-bottom:1px solid #E5E7EB;text-align:right;">{item.get('unit_price', 0)} {currency}</td>
            <td style="padding:10px;border-bottom:1px solid #E5E7EB;text-align:right;font-weight:600;">{item.get('line_total', 0)} {currency}</td>
        </tr>
        """

    text_content = (
        f"Hello {guest_name},\n\n"
        f"Your quote for booking {booking_id} is ready.\n"
        f"Total: {total_amount} {currency}\n\n"
        f"Open your dashboard: {dashboard_link}\n\n"
        "Thank you for choosing Vizit Africa."
    )

    html_content = f"""
    <!DOCTYPE html>
    <html><body style="font-family:Arial,sans-serif;background:#F8F9FA;padding:24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E5E7EB;">
        <tr><td style="padding:24px;">
          <h2 style="margin:0 0 12px 0;color:#111827;">Your Quote Is Ready</h2>
          <p style="color:#374151;">Hello {guest_name}, your quote for booking <strong>{booking_id}</strong> is now available.</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;border:1px solid #E5E7EB;border-collapse:collapse;">
            <thead>
              <tr style="background:#F9FAFB;">
                <th style="padding:10px;text-align:left;">Service</th>
                <th style="padding:10px;text-align:center;">Qty</th>
                <th style="padding:10px;text-align:right;">Unit</th>
                <th style="padding:10px;text-align:right;">Total</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            <tfoot>
              <tr>
                <td colspan="3" style="padding:12px;text-align:right;font-weight:700;">Grand Total</td>
                <td style="padding:12px;text-align:right;font-weight:700;color:#2D4685;">{total_amount} {currency}</td>
              </tr>
            </tfoot>
          </table>
          <div style="margin-top:24px;">
            <a href="{dashboard_link}" style="display:inline-block;padding:12px 18px;background:#2D4685;color:white;text-decoration:none;">View in Dashboard</a>
          </div>
        </td></tr>
      </table>
    </body></html>
    """

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        return msg.send()
    except Exception as e:
        print(f"Client quote email failed: {e}")
        return 0
