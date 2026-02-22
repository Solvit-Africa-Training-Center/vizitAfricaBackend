from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.timezone import now
from .models import Vendor
from .serializers import VendorSerializer
from .permissions import IsVendorOwner


from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db.models import Count, Sum
from accounts.models import User
from bookings.models import BookingItem
from bookings.serializers import BookingItemSerializer

class VendorViewSet(ModelViewSet):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated, IsVendorOwner]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Vendor.objects.none()
        if self.request.user.role == User.Role.ADMIN:
            return Vendor.objects.all()
        return Vendor.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """Public endpoint for vendor registration."""
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
             return Response({"error": "A user with this email already exists"}, status=status.HTTP_400_BAD_REQUEST)
             
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                full_name=request.data.get('name', 'Vendor'),
                phone_number=request.data.get('phone', ''),
                role=User.Role.VENDOR,
                is_active=False # Pending admin approval/verification
            )
            user.set_unusable_password()
            user.save()
            
            vendor = Vendor.objects.create(
                user=user,
                business_name=request.data.get('business_name', user.full_name),
                vendor_type=request.data.get('type', 'other'),
                status='pending'
            )
            
            # TODO: Trigger notification to admin
            
        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Return stats for the vendor's dashboard."""
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor profile not found"}, status=status.HTTP_404_NOT_FOUND)
            
        items = BookingItem.objects.filter(service__user=request.user)
        
        stats = {
            "active_requests": items.filter(status='reserved').count(),
            "upcoming_bookings": items.filter(status='booked', start_date__gte=now().date()).count(),
            "total_revenue": items.filter(status='booked').aggregate(Sum('subtotal'))['subtotal__sum'] or 0
        }
        return Response(stats)

    @action(detail=False, methods=['get'])
    def requests(self, request):
        """List booking items assigned to this vendor."""
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
             return Response({"error": "Vendor profile not found"}, status=status.HTTP_404_NOT_FOUND)

        # Filtering logic per vendor type
        items = BookingItem.objects.filter(service__user=request.user)
        
        # If Car Rental, they might want to see all car items regardless of specific service assignment
        # or we rely strictly on service.user matching which is cleaner
        
        serializer = BookingItemSerializer(items, many=True)
        return Response(serializer.data)