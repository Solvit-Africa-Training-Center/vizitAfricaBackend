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

    # Build verification link (URL-encode email and token)
    # Ensure values are strings before URL-encoding (some token generators may return bytes)
    verification_link = (
        "https://vizit-africa.vercel.app/en/verify-email?"
        f"email={quote_plus(str(recipient_email))}&token={quote_plus(str(code))}"
    )

    # Plain text version
    text_content = (
        f"Verify your Vizit Africa account by visiting the link below:\n\n{verification_link}\n\n"
        "If you did not request this, please ignore this email."
    )

    # HTML version with a CTA button and fallback link
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <tr>
                            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: bold;">Vizit Africa</h1>
                                <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">Your Gateway to African Adventures</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 30px; text-align: center;">
                                <h2 style="color: #333333; margin: 0 0 20px 0; font-size: 24px;">Verify Your Account</h2>
                                <p style="color: #666666; font-size: 16px; line-height: 1.6; margin: 0 0 30px 0;">
                                    Thank you for registering with Vizit Africa! Click the button below to verify your email address.
                                </p>
                                <div style="padding: 30px 0;">
                                    <a href="{verification_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 6px; display: inline-block; font-weight: bold;">Verify Email</a>
                                </div>
                                <p style="color: #666666; font-size: 14px; line-height: 1.6; margin: 30px 0 0 0;">
                                    If the button does not work, copy and paste the following link into your browser:
                                </p>
                                <p style="word-break: break-all; color: #1a73e8; font-size: 13px;">{verification_link}</p>
                                <p style="color: #666666; font-size: 14px; line-height: 1.6; margin: 20px 0 0 0;">
                                    This link will expire in <strong>10 minutes</strong>. If you didn't request this, please ignore this email.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;">
                                <p style="color: #999999; font-size: 12px; margin: 0 0 10px 0;">This is an automated message, please do not reply.</p>
                                <p style="color: #999999; font-size: 12px; margin: 0;">© 2024 Vizit Africa. All rights reserved.</p>
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
        # Logging would be better in production - keep print for local debug
        print(f"Email sending failed: {e}")
        return 0
