from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User, VerificationCode
from accounts.utils.code_generator import generate_verification_code
from accounts.utils.send_email import send_verification_email
from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework import serializers
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User



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

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            phone_number=validated_data["phone_number"],
            bio=validated_data.get("bio", ""),
            role=validated_data.get("role", User.CLIENT),
            preferred_currency=validated_data.get("preferred_currency", "USD"),
            is_active=False,  # 🔐 wait for email verification
        )

        code = generate_verification_code()

        VerificationCode.objects.create(
            user=user,
            code=code,
            purpose=VerificationCode.SIGNUP,
        )

        send_verification_email(user.email, code)

        return user


# ===================================================
# EMAIL VERIFICATION
# ===================================================
class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        try:
            user = User.objects.get(email=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "User not found"})

        try:
            verification = VerificationCode.objects.get(
                user=user,
                code=attrs["code"],
                purpose=VerificationCode.SIGNUP,
                is_used=False,
            )
        except VerificationCode.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid code"})

        if not verification.is_valid:
            raise serializers.ValidationError({"code": "Code expired"})

        attrs["user"] = user
        attrs["verification"] = verification
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

