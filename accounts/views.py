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


from accounts.services import AccountService, SavedItemService
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
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def verify_email(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Service already performed activation during validation
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
                "user": UserSerializer(user).data
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


from accounts.serializers import SavedItemSerializer, UserSerializer
from accounts.models import SavedItem

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
             
        saved_item = SavedItemService.save_item(
            user=request.user,
            item_type=item_type,
            item_id=item_id
        )
        
        serializer = self.get_serializer(saved_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        item_type = request.data.get('type')
        item_id = request.data.get('id')
        
        if not item_type or not item_id:
             return Response({'error': 'Type and ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        removed = SavedItemService.remove_item(
            user=request.user,
            item_type=item_type,
            item_id=item_id
        )
        
        if removed:
            return Response({'message': 'Item removed'}, status=status.HTTP_200_OK)
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
