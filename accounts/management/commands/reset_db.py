from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from vendors.models import Vendor
from services.models import Service, ServiceAvailability, Discount, ServiceMedia
from locations.models import Location
from bookings.models import Booking, BookingItem, Package, PackageItem
from payments.models import Payment
from transactions.models import Transaction
from tickets.models import Ticket
from accounts.models import SavedItem, VerificationCode

User = get_user_model()

class Command(BaseCommand):
    help = "Reset database to only an admin and no other data"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Resetting database...")
        
        # 1. Clear existing data
        self.stdout.write("Clearing existing data...")
        
        # We delete in reverse order of dependencies where possible
        Ticket.objects.all().delete()
        Transaction.objects.all().delete()
        Payment.objects.all().delete()
        
        BookingItem.objects.all().delete()
        Booking.objects.all().delete()
        PackageItem.objects.all().delete()
        Package.objects.all().delete()
        
        ServiceAvailability.objects.all().delete()
        ServiceMedia.objects.all().delete()
        Discount.objects.all().delete()
        Service.objects.all().delete()
        
        Vendor.objects.all().delete()
        Location.objects.all().delete()
        
        SavedItem.objects.all().delete()
        VerificationCode.objects.all().delete()
        User.objects.all().delete()

        # 2. Create Super Admin
        self.stdout.write("Creating super admin...")
        admin = User.objects.create_superuser(
            email="admin@vizit.africa",
            password="password123",
            full_name="Vizit Africa Admin",
            phone_number="+250780000000",
            role="ADMIN",
            is_active=True
        )

        self.stdout.write(self.style.SUCCESS("Database reset successfully!"))
        self.stdout.write(self.style.WARNING("Access Credentials:"))
        self.stdout.write("  Admin: admin@vizit.africa / password123")
