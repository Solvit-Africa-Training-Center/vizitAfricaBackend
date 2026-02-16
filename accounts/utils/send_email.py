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
