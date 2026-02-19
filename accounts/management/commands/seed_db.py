import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from vendors.models import Vendor
from services.models import Service, ServiceAvailability, Discount
from locations.models import Location
from bookings.models import Booking, BookingItem
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Command(BaseCommand):
    help = "Seed database with initial data for MVP"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding database...")
        
        # 1. Clear existing data
        self.stdout.write("Clearing existing data...")
        BookingItem.objects.all().delete()
        Booking.objects.all().delete()
        ServiceAvailability.objects.all().delete()
        Discount.objects.all().delete()
        Service.objects.all().delete()
        Vendor.objects.all().delete()
        Location.objects.all().delete()
        # Keep superuser if possible, or just delete all non-superusers?
        # For a clean seed, let's delete all and recreate.
        User.objects.all().delete()

        # 2. Locations
        self.stdout.write("Creating locations...")
        locations = [
            Location.objects.create(name="Kigali", latitude=-1.9441, longitude=30.0619),
            Location.objects.create(name="Musanze", latitude=-1.5000, longitude=29.6333),
            Location.objects.create(name="Rubavu", latitude=-1.6700, longitude=29.2500),
            Location.objects.create(name="Akagera", latitude=-1.8833, longitude=30.7167),
        ]

        # 3. Users
        self.stdout.write("Creating users...")
        
        # Super Admin
        admin = User.objects.create_superuser(
            email="admin@vizit.africa",
            password="password123",
            full_name="Admin User",
            role="ADMIN",
            is_active=True
        )

        # Vendors
        vendor_user_1 = User.objects.create_user(
            email="vendor1@vizit.africa",
            password="password123",
            full_name="John Vendor",
            role="VENDOR",
            is_active=True
        )
        
        vendor_user_2 = User.objects.create_user(
            email="vendor2@vizit.africa",
            password="password123",
            full_name="Sarah Guide",
            role="VENDOR",
            is_active=True
        )
        
        # Pending Vendor
        vendor_user_3 = User.objects.create_user(
            email="pending@vizit.africa",
            password="password123",
            full_name="New Applicant",
            role="VENDOR",
            is_active=True
        )

        # Client
        client_user = User.objects.create_user(
            email="client@vizit.africa",
            password="password123",
            full_name="Alice Traveler",
            role="CLIENT",
            is_active=True
        )

        # 4. Vendor Profiles
        self.stdout.write("Creating vendor profiles...")
        
        v1 = Vendor.objects.create(
            user=vendor_user_1,
            business_name="Kigali Luxury Hotels",
            vendor_type="hotel",
            is_approved=True,
            address="Kigali, Rwanda"
        )
        
        v2 = Vendor.objects.create(
            user=vendor_user_2,
            business_name="Gorilla Trekking Tours",
            vendor_type="guide",
            is_approved=True,
            address="Musanze, Rwanda"
        )
        
        v3 = Vendor.objects.create(
            user=vendor_user_3,
            business_name="Pending Adventures",
            vendor_type="experience",
            is_approved=False,
            address="Rubavu, Rwanda"
        )

        # 5. Services
        self.stdout.write("Creating services...")
        
        s1 = Service.objects.create(
            user=v1.user,
            title="Luxury Suite Stay",
            description="Experience comfort in the heart of Kigali.",
            service_type="hotel",
            base_price=150.00,
            currency="USD",
            location=locations[0],
            status="active",
            capacity=10
        )
        
        s2 = Service.objects.create(
            user=v2.user,
            title="Volcanoes Gorilla Trek",
            description="Once in a lifetime experience.",
            service_type="tour",
            base_price=1500.00,
            currency="USD",
            location=locations[1],
            status="active",
            capacity=8
        )
        
        s3 = Service.objects.create(
            user=v1.user,
            title="Airport Transfer",
            description="Pick up and drop off.",
            service_type="tour", # Changed to tour as transport is not in ServiceType choices
            base_price=30.00,
            currency="USD",
            location=locations[0],
            status="active",
            capacity=4
        )
        
        Service.objects.create(
            user=v2.user,
            title="Musanze Caves Tour",
            description="Explore the caves.",
            service_type="experience",
            base_price=50.00,
            currency="USD",
            location=locations[1],
            status="pending", # map 'draft' to 'pending' or 'inactive', model has 'pending'
            capacity=20
        )

        # 6. Availabilities (Simple)
        today = timezone.now().date()
        for service in [s1, s2, s3]:
            # Create availability for next 30 days
            for i in range(30):
                date = today + timedelta(days=i)
                ServiceAvailability.objects.create(
                    service=service,
                    start_date=date,
                    end_date=date,
                    available_quantity=service.capacity,
                    price_override=None
                )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
        self.stdout.write(self.style.WARNING("Accounts:"))
        self.stdout.write("  Admin: admin@vizit.africa / password123")
        self.stdout.write("  Vendor 1: vendor1@vizit.africa / password123")
        self.stdout.write("  Vendor 2: vendor2@vizit.africa / password123")
        self.stdout.write("  Client: client@vizit.africa / password123")
