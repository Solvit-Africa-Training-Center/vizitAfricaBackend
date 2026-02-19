import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import MinLengthValidator, MaxLengthValidator
import datetime
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# ===================================================
# SAVED ITEM MODEL
# ===================================================
class SavedItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_items')
    
    # Generic Foreign Key
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField() # Assuming all our models use UUIDs
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f"{self.user.email} saved {self.content_object}"

# ===================================================
# USER MANAGER
# ===================================================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("Email is required"))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


# ===================================================
# USER MODEL
# ===================================================
class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = "CLIENT", _("Client")
        VENDOR = "VENDOR", _("Vendor")
        ADMIN = "ADMIN", _("Admin")

    # Role Constants for easy access
    CLIENT = Role.CLIENT
    VENDOR = Role.VENDOR
    ADMIN = Role.ADMIN

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=13,
        validators=[
            MinLengthValidator(10),
            MaxLengthValidator(13),
        ],
    )

    bio = models.TextField(blank=True, null=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
    )

    preferred_currency = models.CharField(
        max_length=10,
        default="USD",
    )

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone_number"]

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_vendor(self):
        return self.role == self.Role.VENDOR


class VerificationCode(models.Model):
    class Purpose(models.TextChoices):
        SIGNUP = "SIGNUP", _("Signup")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="verification_codes"
    )
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ("user", "code")

    @property
    def is_valid(self):
        expiry_time = self.created_at + datetime.timedelta(minutes=10)
        return timezone.now() < expiry_time and not self.is_used


