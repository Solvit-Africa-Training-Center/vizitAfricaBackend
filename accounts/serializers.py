from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User, VerificationCode, SavedItem
from accounts.utils.code_generator import generate_verification_code
from accounts.utils.send_email import send_verification_email
from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework import serializers
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "bio",
            "role",
            "preferred_currency",
            "is_active",
            "created_at",
            "vendor_profile",
        )
        read_only_fields = ("id", "email", "role", "is_active", "created_at")

    def get_vendor_profile(self, obj):
        if hasattr(obj, 'vendor_profile'):
            return {
                'id': obj.vendor_profile.id,
                'business_name': obj.vendor_profile.business_name,
                'is_approved': obj.vendor_profile.is_approved
            }
        return None

    vendor_profile = serializers.SerializerMethodField()


class SavedItemSerializer(serializers.ModelSerializer):
    # We can try to serialize the content_object generically or just return ID/Type
    content_object = serializers.SerializerMethodField()
    
    class Meta:
        model = SavedItem
        fields = ('id', 'created_at', 'object_id', 'content_object')
        
    def get_content_object(self, obj):
        # basic info about the saved object
        if not obj.content_object:
            return None
            
        data = {
            'id': str(obj.object_id),
            'type': obj.content_type.model,
            'title': str(obj.content_object)
        }
        
        # Try to get more specific fields if they exist
        if hasattr(obj.content_object, 'title'):
            data['title'] = obj.content_object.title
        elif hasattr(obj.content_object, 'name'):
            data['title'] = obj.content_object.name
            
        if hasattr(obj.content_object, 'description'):
            data['description'] = obj.content_object.description
            
        # Add image if available (Service/Experience usually has media)
        if hasattr(obj.content_object, 'media') and obj.content_object.media.exists():
            data['image'] = obj.content_object.media.first().media_url
            
        return data

from accounts.services import AccountService, SavedItemService

# ===================================================
# USER REGISTRATION
# ===================================================
class UserRegisterSerializer(serializers.ModelSerializer):
    re_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "phone_number",
            "bio",
            "role",
            "preferred_currency",
            "password",
            "re_password",
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "role": {"read_only": True},
        }

    def validate_role(self, value):
        if value == User.ADMIN:
            raise serializers.ValidationError("Cannot register as admin.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["re_password"]:
            raise serializers.ValidationError(
                {"password": "Passwords do not match"}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("re_password")
        
        # Use service to handle registration logic
        return AccountService.register_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            phone_number=validated_data["phone_number"],
            bio=validated_data.get("bio", ""),
            role=validated_data.get("role", User.CLIENT),
            preferred_currency=validated_data.get("preferred_currency", "USD"),
        )


# ===================================================
# EMAIL VERIFICATION
# ===================================================
class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        # Service handles validation and activation
        # This will raise ValidationError if invalid
        user = AccountService.verify_email(
            email=attrs["email"],
            code=attrs["code"]
        )
        attrs["user"] = user
        return attrs


# ===================================================
# JWT LOGIN (BLOCK UNVERIFIED USERS)
# ===================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.is_active:
            raise serializers.ValidationError(
                "Account not activated. Please verify your email."
            )

        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": self.user.role,
        }

        return data

class GoogleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get("token")

        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception:
            raise serializers.ValidationError("Invalid Google token")

        email = idinfo.get("email")
        full_name = idinfo.get("name")

        if not email:
            raise serializers.ValidationError("Email not provided by Google")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "phone_number": "",  # Placeholder, user should update profile
                "is_active": True, 
            },
        )

        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
        }


from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

class SetPasswordSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)
    re_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["re_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        
        # Validation logic is now in Service too, but DRF validation is also fine here.
        # Let's keep the service call in save() to be consistent.
        return attrs

    def save(self):
        # Use service to handle password setting logic
        return AccountService.set_password(
            uidb64=self.validated_data["uidb64"],
            token=self.validated_data["token"],
            password=self.validated_data["password"]
        )


