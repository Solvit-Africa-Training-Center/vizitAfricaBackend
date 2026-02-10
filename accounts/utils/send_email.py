from django.conf import settings
from django.core.mail import EmailMultiAlternatives

def send_verification_email(recipient_email, code):
    subject = "Verify Your Vizit Africa Account"
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [recipient_email]
    
    # Plain text version
    text_content = f"Your verification code is: {code}"
    
    # HTML version
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
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: bold;">Vizit Africa</h1>
                                <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">Your Gateway to African Adventures</p>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h2 style="color: #333333; margin: 0 0 20px 0; font-size: 24px;">Verify Your Account</h2>
                                <p style="color: #666666; font-size: 16px; line-height: 1.6; margin: 0 0 30px 0;">
                                    Thank you for registering with Vizit Africa! To complete your registration, please use the verification code below:
                                </p>
                                
                                <!-- OTP Box -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 20px 40px; display: inline-block;">
                                                <span style="color: #ffffff; font-size: 32px; font-weight: bold; letter-spacing: 8px; font-family: 'Courier New', monospace;">{code}</span>
                                            </div>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="color: #666666; font-size: 14px; line-height: 1.6; margin: 30px 0 0 0;">
                                    This code will expire in <strong>10 minutes</strong>. If you didn't request this code, please ignore this email.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;">
                                <p style="color: #999999; font-size: 12px; margin: 0 0 10px 0;">
                                    This is an automated message, please do not reply.
                                </p>
                                <p style="color: #999999; font-size: 12px; margin: 0;">
                                    © 2024 Vizit Africa. All rights reserved.
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
