from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Service, ServiceMedia, ServiceAvailability, Discount
from .serializers import ServiceSerializer, ServiceMediaSerializer, ServiceAvailabilitySerializer, DiscountSerializer
from .permissions import IsApprovedVendor

class ServiceViewSet(ModelViewSet):
    serializer_class = ServiceSerializer
    
    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve':
            return [AllowAny()]
        return [IsAuthenticated(), IsApprovedVendor()]

    def get_queryset(self):
        if self.action == 'list' or self.action == 'retrieve':
            return Service.objects.filter(status='active')
        from accounts.models import User
        user = self.request.user
        if hasattr(user, 'role') and user.role == User.ADMIN:
            return Service.objects.all()
        return Service.objects.filter(user=user)

    def perform_create(self, serializer):
        from accounts.models import User
        user = self.request.user
        if hasattr(user, 'role') and user.role == User.ADMIN:
            # Admin must specify the user/vendor in the request data
            if 'user' not in serializer.validated_data:
                serializer.save(user=user)
            else:
                serializer.save()
        else:
            serializer.save(user=user)


class ServiceMediaViewSet(ModelViewSet):
    serializer_class = ServiceMediaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ServiceMedia.objects.filter(service__user=self.request.user) 


class ServiceAvailabilityViewSet(ModelViewSet):
    serializer_class = ServiceAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ServiceAvailability.objects.filter(service__user=self.request.user)


class DiscountViewSet(ModelViewSet):
    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'vendor'):
            return Discount.objects.filter(vendor=user.vendor) | Discount.objects.filter(vendor__isnull=True)
        return Discount.objects.filter(vendor__isnull=True)