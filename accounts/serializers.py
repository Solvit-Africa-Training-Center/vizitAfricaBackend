from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User, VerificationCode
from accounts.utils.code_generator import generate_verification_code
from accounts.utils.send_email import send_verification_email


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

# ===================================================
# PASSWORD SETTING (FOR GUESTS)
# ===================================================
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

class SetPasswordSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    re_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["re_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        
        try:
            uid = urlsafe_base64_decode(attrs['uidb64']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": "Invalid user ID"})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Invalid or expired token"})

        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.is_active = True  # Activate the guest account
        user.save()
        return user
