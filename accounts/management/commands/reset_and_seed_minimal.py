from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.contrib.auth import get_user_model
from accounts.models import User
from vendors.models import Vendor
from services.models import Service, ServiceMedia, ServiceAvailability, Discount
from locations.models import Location
from bookings.models import Booking, BookingItem, Package, PackageItem
from payments.models import Payment
from transactions.models import Transaction
from tickets.models import Ticket
from accounts.models import SavedItem, VerificationCode

User = get_user_model()

class Command(BaseCommand):
    help = "Reset database to only admin and seed services (no bookings/clients)"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Resetting and seeding minimal data...")
        
        # 1. Clear existing data
        self.stdout.write("Clearing existing data...")
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
        self.stdout.write(self.style.SUCCESS(f"  Created admin: {admin.email} / password123"))

        # 3. Use seed_services logic but skip bookings and clients
        # To avoid duplicating code, we can just call seed_services 
        # but seed_services adds clients and bookings.
        # Let's modify seed_services to be more modular or just run the core parts here.
        
        from services.management.commands.seed_services import Command as SeedServicesCommand
        seeder = SeedServicesCommand()
        seeder.stdout = self.stdout
        seeder.style = self.style
        
        self.stdout.write("Seeding vendors...")
        vendors_map = seeder._seed_vendors(admin)
        
        self.stdout.write("Seeding locations...")
        locations_map = seeder._seed_locations()
        
        self.stdout.write("Seeding services...")
        created, skipped, all_services = seeder._seed_services(vendors_map, locations_map)
        
        self.stdout.write("Seeding availabilities...")
        seeder._seed_availabilities(all_services)

        self.stdout.write(self.style.SUCCESS("Database reset and services seeded successfully!"))
