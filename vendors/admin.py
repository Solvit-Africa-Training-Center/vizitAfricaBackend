from django.contrib import admin
from .models import Vendor
from accounts.models import User

class VendorAdmin(admin.ModelAdmin):
	def save_model(self, request, obj, form, change):
		if hasattr(request.user, 'role') and request.user.role == User.ADMIN:
			obj.is_approved = True
			obj.approved_by = request.user
		super().save_model(request, obj, form, change)

admin.site.register(Vendor, VendorAdmin)