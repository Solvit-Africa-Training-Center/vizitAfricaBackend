import logging
from django.db import transaction
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType

from accounts.models import User, VerificationCode, SavedItem
from accounts.utils.code_generator import generate_verification_code
from accounts.utils.send_email import send_verification_email

logger = logging.getLogger(__name__)

class AccountService:
    @staticmethod
    @transaction.atomic
    def register_user(email: str, password: str, full_name: str, phone_number: str, **extra_fields) -> User:
        """Register a new user and send verification email."""
        if User.objects.filter(email=email).exists():
             raise ValidationError({"email": "User with this email already exists."})
             
        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone_number=phone_number,
            is_active=False,
            **extra_fields
        )

        code = generate_verification_code()
        VerificationCode.objects.create(
            user=user,
            code=code,
            purpose=VerificationCode.Purpose.SIGNUP,
        )

        try:
             send_verification_email(user.email, code)
        except Exception as e:
             logger.error(f"Failed to send verification email to {email}: {e}")
             # We might not want to fail the whole registration if email fails?
             # Or we do. Usually it's better to let user know.
             
        return user

    @staticmethod
    @transaction.atomic
    def verify_email(email: str, code: str) -> User:
        """Verify email using the code and activate user."""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError({"email": "User not found"})

        try:
            verification = VerificationCode.objects.get(
                user=user,
                code=code,
                purpose=VerificationCode.Purpose.SIGNUP,
                is_used=False,
            )
        except VerificationCode.DoesNotExist:
            raise ValidationError({"code": "Invalid or already used code"})

        if not verification.is_valid:
            raise ValidationError({"code": "Verification code has expired"})

        user.is_active = True
        user.save()

        verification.is_used = True
        verification.save()
        
        return user

    @staticmethod
    @transaction.atomic
    def set_password(uidb64: str, token: str, password: str) -> User:
        """Set a new password for a user using a reset/set token."""
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise ValidationError({"token": "Invalid user identification"})

        if not default_token_generator.check_token(user, token):
            raise ValidationError({"token": "Invalid or expired token"})

        user.set_password(password)
        user.is_active = True # Activating if they set a password from an invite/guest flow
        user.save()
        
        return user

class SavedItemService:
    @staticmethod
    def save_item(user: User, item_type: str, item_id: str) -> SavedItem:
        """Save an item (Service, Experience, etc.) for a user."""
        
        # Mapping simple names to app labels/models
        # This mapping can be moved to a configuration or the model itself
        TYPE_MAPPING = {
             'service': ('services', 'service'),
             'experience': ('services', 'service'), # Experience is a Service subtype or alias
             'hotel': ('locations', 'hotel'), # Just an example if you have hotels
             'accommodation': ('locations', 'accommodation'),
             'booking': ('bookings', 'booking'),
        }
        
        app_label, model_name = TYPE_MAPPING.get(item_type, (None, item_type))
        
        try:
            if app_label:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
            else:
                ct = ContentType.objects.get(model=model_name)
        except ContentType.DoesNotExist:
            raise ValidationError({"type": f"Invalid item type: {item_type}"})

        # Check if already saved
        saved_item, created = SavedItem.objects.get_or_create(
            user=user,
            content_type=ct,
            object_id=item_id
        )
        
        return saved_item

    @staticmethod
    def remove_item(user: User, item_type: str, item_id: str) -> bool:
        """Remove a saved item."""
        # Similar mapping
        TYPE_MAPPING = {
             'service': ('services', 'service'),
             'experience': ('services', 'service'),
        }
        
        app_label, model_name = TYPE_MAPPING.get(item_type, (None, item_type))
        
        try:
            if app_label:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
            else:
                ct = ContentType.objects.get(model=model_name)
        except ContentType.DoesNotExist:
            raise ValidationError({"type": f"Invalid item type: {item_type}"})

        deleted, _ = SavedItem.objects.filter(user=user, content_type=ct, object_id=item_id).delete()
        return bool(deleted)
