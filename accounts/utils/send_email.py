from django.conf import settings
from django.core.mail import send_mail

def send_verification_email(recipient_email, code):
    subject = "Verify your account"
    message = f"Hello,\n\nYour verification code is: {code}\n\nThank you for registering."
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [recipient_email]

    try:
        return send_mail(subject, message, from_email, recipient_list)
    except Exception as e:
        print(f"Email sending failed: {e}")
        return 0
