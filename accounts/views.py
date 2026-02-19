from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.serializers import GoogleLoginSerializer


from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import (
    UserRegisterSerializer,
    VerifyEmailSerializer,
    CustomTokenObtainPairSerializer,
)
from accounts.permissions import IsAdmin


class UserViewSet(viewsets.ModelViewSet):
    """
    Endpoints:
    - POST /api/accounts/users/           → Register
    - GET  /api/accounts/users/           → List users (admin)
    - GET  /api/accounts/users/profile/   → Logged-in profile
    - POST /api/accounts/users/verify_email/ → Activate account
    """

    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        if self.action == "list":
            return [IsAdmin()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().only(
            "id", "full_name", "email", "role", "created_at"
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def verify_email(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        verification = serializer.validated_data["verification"]

        user.is_active = True
        user.save()

        verification.is_used = True
        verification.save()

        return Response(
            {"message": "Account activated successfully"},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def set_password(self, request):
        from .serializers import SetPasswordSerializer
        from rest_framework_simplejwt.tokens import RefreshToken

        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Password set successfully. You are now logged in.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                }
            },
            status=status.HTTP_200_OK,
        )


class LoginViewSet(TokenObtainPairView):
    """
    POST /api/accounts/login/
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


from accounts.serializers import SavedItemSerializer
from accounts.models import SavedItem
from django.contrib.contenttypes.models import ContentType

class SavedItemViewSet(viewsets.ModelViewSet):
    serializer_class = SavedItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SavedItem.objects.filter(user=self.request.user)
        
    def create(self, request, *args, **kwargs):
        # Expecting { type: "service", id: "uuid" }
        item_type = request.data.get('type')
        item_id = request.data.get('id')
        
        if not item_type or not item_id:
             return Response({'error': 'Type and ID are required'}, status=status.HTTP_400_BAD_REQUEST)
             
        # Resolve Content Type
        # Mapping simple names to actual models if needed, or rely on app_label.model
        # For now, let's assume 'service' maps to 'services.service'
        
        app_label = 'services' if item_type in ['service', 'experience'] else 'bookings' # fallback
        model_name = item_type if item_type != 'experience' else 'service' # Experience is a Service
        
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
             # Try generic lookup
             try:
                 ct = ContentType.objects.get(model=item_type)
             except ContentType.DoesNotExist:
                 return Response({'error': f'Invalid type: {item_type}'}, status=status.HTTP_400_BAD_REQUEST)
                 
        # Check if already saved
        if SavedItem.objects.filter(user=request.user, content_type=ct, object_id=item_id).exists():
             return Response({'message': 'Item already saved'}, status=status.HTTP_200_OK)
             
        saved_item = SavedItem.objects.create(
            user=request.user,
            content_type=ct,
            object_id=item_id
        )
        
        serializer = self.get_serializer(saved_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        # Custom remove endpoint taking type/id
        item_type = request.data.get('type')
        item_id = request.data.get('id')
        
        if not item_type or not item_id:
             return Response({'error': 'Type and ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        app_label = 'services' if item_type in ['service', 'experience'] else 'bookings'
        model_name = item_type if item_type != 'experience' else 'service'
        
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
             try:
                 ct = ContentType.objects.get(model=item_type)
             except ContentType.DoesNotExist:
                 return Response({'error': f'Invalid type: {item_type}'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = SavedItem.objects.filter(user=request.user, content_type=ct, object_id=item_id).delete()
        
        if deleted:
            return Response({'message': 'Item removed'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


from django.core.mail import send_mail
from django.conf import settings

class ContactView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        message = request.data.get('message')
        subject = request.data.get('subject', 'New Contact Form Submission')
        
        if not all([name, email, message]):
            return Response({'error': 'Name, email and message are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Send email to admin
            send_mail(
                subject=f"Contact: {subject}",
                message=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[getattr(settings, 'ADMIN_EMAIL', 'admin@vizit-africa.com')], 
                fail_silently=False,
            )
            return Response({'message': 'Message sent successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Contact form error: {e}")
            return Response({'error': 'Failed to send message'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
