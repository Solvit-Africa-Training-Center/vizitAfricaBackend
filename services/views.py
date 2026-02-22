from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Service, ServiceMedia, ServiceAvailability, Discount
from .serializers import ServiceSerializer, ServiceMediaSerializer, ServiceAvailabilitySerializer, DiscountSerializer
from .permissions import IsApprovedVendor

from rest_framework.decorators import action
from rest_framework.response import Response

class ServiceViewSet(ModelViewSet):
    serializer_class = ServiceSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'check_availability']:
            return [AllowAny()]
        return [IsAuthenticated(), IsApprovedVendor()]

    @action(detail=False, methods=['post'], url_path='check-availability')
    def check_availability(self, request):
        """
        Public/Internal endpoint to check capacity.
        Payload: { service_id, start_date, end_date, quantity }
        """
        service_id = request.data.get('service_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        quantity = int(request.data.get('quantity', 1))

        if not all([service_id, start_date, end_date]):
            return Response({"error": "service_id, start_date, and end_date are required"}, status=400)

        # Basic capacity check logic
        availabilities = ServiceAvailability.objects.filter(
            service_id=service_id,
            start_date__lte=end_date,
            end_date__gte=start_date
        )

        reasons = []
        if not availabilities.exists():
            # If no records, we might want to check the base service capacity
            service = Service.objects.filter(id=service_id).first()
            if service and service.capacity < quantity:
                reasons.append(f"Requested quantity {quantity} exceeds base capacity {service.capacity}")
        else:
            for av in availabilities:
                if av.is_blocked:
                    reasons.append(f"Blocked for period starting {av.start_date}")
                if av.available_quantity < quantity:
                    reasons.append(f"Insufficient capacity on {av.start_date}: requested {quantity}, available {av.available_quantity}")

        return Response({
            "available": len(reasons) == 0,
            "reasons": reasons
        })

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
            # For admin requests, allow optional user and fallback to request user.
            selected_user = serializer.validated_data.get('user')
            if selected_user is None:
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
