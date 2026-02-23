from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils.timezone import now
from django.db.models import Sum

from accounts.models import User
from bookings.models import BookingItem
from bookings.serializers import BookingItemSerializer
from .models import Vendor
from .serializers import VendorSerializer
from .permissions import IsVendorOwner
from accounts.permissions import IsAdmin


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
        """public endpoint for vendor registration"""
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
                is_active=False
            )
            user.set_unusable_password()
            user.save()

            vendor = Vendor.objects.create(
                user=user,
                business_name=request.data.get('business_name', user.full_name),
                vendor_type=request.data.get('type', 'other'),
                status='pending'
            )

        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdmin])
    def approve(self, request, pk=None):
        """admin-only: approve a vendor and activate their account"""
        vendor = self.get_object()
        vendor.is_approved = True
        vendor.status = Vendor.Status.ACTIVE
        vendor.approved_by = request.user
        vendor.approved_on = now()
        vendor.save()

        vendor.user.is_active = True
        vendor.user.save()

        return Response(VendorSerializer(vendor).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def confirm_item(self, request, pk=None):
        """vendor: confirm a specific booking item assigned to them"""
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor profile not found"}, status=status.HTTP_404_NOT_FOUND)

        item = BookingItem.objects.filter(
            id=pk,
            service__user=request.user
        ).first()

        if not item:
            return Response({"error": "Booking item not found"}, status=status.HTTP_404_NOT_FOUND)

        item.status = 'booked'
        item.save()

        return Response(BookingItemSerializer(item).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """return stats for the vendor's dashboard"""
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
        """list booking items assigned to this vendor"""
        vendor = Vendor.objects.filter(user=request.user).first()
        if not vendor:
            return Response({"error": "Vendor profile not found"}, status=status.HTTP_404_NOT_FOUND)

        items = BookingItem.objects.filter(service__user=request.user)
        serializer = BookingItemSerializer(items, many=True)
        return Response(serializer.data)