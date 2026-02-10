from rest_framework.permissions import BasePermission

class IsApprovedVendor(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        # Allow admins using User.ADMIN constant
        from accounts.models import User
        if hasattr(user, 'role') and user.role == User.ADMIN:
            return True
        return hasattr(user, 'vendor') and user.vendor.is_approved
