from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.timezone import now
from .models import Vendor
from .serializers import VendorSerializer
from .permissions import IsVendorOwner


class VendorViewSet(ModelViewSet):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated, IsVendorOwner]

    def get_queryset(self):
        if self.request.user and self.request.user.role == 'admin':
            return Vendor.objects.all()
        return Vendor.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        user = self.request.user
        from accounts.models import User
        vendor_data = {'user': user}
        if hasattr(user, 'role') and user.role == User.ADMIN:
            vendor_data['is_approved'] = True
            vendor_data['approved_by'] = user
        serializer.save(**vendor_data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        vendor = self.get_object()
        vendor.is_approved = True
        vendor.approved_by = request.user
        vendor.approved_on = now()
        vendor.save()
        return Response({"status": "Vendor approved"})