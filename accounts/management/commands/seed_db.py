import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from vendors.models import Vendor
from services.models import Service, ServiceAvailability, Discount
from locations.models import Location
from bookings.models import Booking, BookingItem
from django.utils import timezone
from datetime import timedelta, time
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "Seed database with realistic initial data for Vizit Africa"

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
        User.objects.all().delete()

        # 2. Locations
        self.stdout.write("Creating locations...")
        locations_data = [
            {"name": "Kigali", "latitude": -1.9441, "longitude": 30.0619},
            {"name": "Musanze", "latitude": -1.5000, "longitude": 29.6333},
            {"name": "Rubavu", "latitude": -1.6700, "longitude": 29.2500},
            {"name": "Akagera", "latitude": -1.8833, "longitude": 30.7167},
            {"name": "Nyungwe", "latitude": -2.4833, "longitude": 29.2333},
            {"name": "Karongi", "latitude": -2.1583, "longitude": 29.3514},
        ]
        locations = [Location.objects.create(**loc) for loc in locations_data]

        # 3. Users
        self.stdout.write("Creating users...")
        
        # Super Admin
        admin = User.objects.create_superuser(
            email="admin@vizit.africa",
            password="password123",
            full_name="Vizit Africa Admin",
            phone_number="+250780000000",
            role="ADMIN",
            is_active=True
        )

        # Vendors
        vendor_configs = [
            {"email": "stay@kigaliluxury.rw", "name": "Kigali Luxury Retreats", "phone": "+250781111111", "type": "hotel"},
            {"email": "info@gorillaguides.rw", "name": "Silverback Expedition Guides", "phone": "+250782222222", "type": "guide"},
            {"email": "travel@akagerapark.rw", "name": "Akagera Safari Tours", "phone": "+250783333333", "type": "experience"},
            {"email": "wheels@rwanda.rw", "name": "Rwanda Express Car Rentals", "phone": "+250784444444", "type": "car_rental"},
            {"email": "contact@nyungweforest.rw", "name": "Nyungwe Eco-Lodge", "phone": "+250785555555", "type": "hotel"},
        ]

        vendor_profiles = []
        for config in vendor_configs:
            user = User.objects.create_user(
                email=config["email"],
                password="password123",
                full_name=config["name"],
                phone_number=config["phone"],
                role="VENDOR",
                is_active=True
            )
            vendor = Vendor.objects.create(
                user=user,
                business_name=config["name"],
                vendor_type=config["type"],
                is_approved=True,
                address=f"{config['name']} Head Office, Rwanda"
            )
            vendor_profiles.append(vendor)

        # Clients
        client_configs = [
            {"email": "john.doe@example.com", "name": "John Doe", "phone": "+12025550101"},
            {"email": "jane.smith@example.com", "name": "Jane Smith", "phone": "+442079460958"},
        ]
        clients = []
        for config in client_configs:
            client = User.objects.create_user(
                email=config["email"],
                password="password123",
                full_name=config["name"],
                phone_number=config["phone"],
                role="CLIENT",
                is_active=True
            )
            clients.append(client)

        # 4. Services
        self.stdout.write("Creating services...")
        services = []

        # Hotel Services
        services.append(Service.objects.create(
            user=vendor_profiles[0].user,
            location=locations[0],
            title="Presidential Suite - Kigali Luxury",
            service_type="hotel",
            description="Our flagship suite with panoramic views of Kigali's rolling hills. Includes 24/7 butler service and private lounge access.",
            base_price=450.00,
            currency="USD",
            capacity=2,
            status="active"
        ))

        services.append(Service.objects.create(
            user=vendor_profiles[4].user,
            location=locations[4],
            title="Forest View Cabin - Nyungwe Eco-Lodge",
            service_type="hotel",
            description="Immerse yourself in nature. These wooden cabins offer stunning views of the Nyungwe canopy.",
            base_price=280.00,
            currency="USD",
            capacity=2,
            status="active"
        ))

        # Tour/Experience Services
        services.append(Service.objects.create(
            user=vendor_profiles[1].user,
            location=locations[1],
            title="Exclusive Gorilla Trekking Experience",
            service_type="experience",
            description="A full-day guided trek into Volcanoes National Park to encounter the mountain gorillas. Includes permit handling and porter services.",
            base_price=1650.00,
            currency="USD",
            capacity=6,
            status="active"
        ))

        services.append(Service.objects.create(
            user=vendor_profiles[2].user,
            location=locations[3],
            title="Full Day Game Drive - Akagera",
            service_type="tour",
            description="Explore the savannas of Akagera National Park. Encounter elephants, lions, rhinos, and more in a customized 4x4 safari vehicle.",
            base_price=120.00,
            currency="USD",
            capacity=4,
            status="active"
        ))

        # Car Rental Services
        services.append(Service.objects.create(
            user=vendor_profiles[3].user,
            location=locations[0],
            title="Toyota Land Cruiser 4x4 Rental",
            service_type="car",
            description="Reliable 4x4 vehicle perfect for exploring Rwanda's varied terrain. GPS and insurance included.",
            base_price=85.00,
            currency="USD",
            capacity=5,
            status="active"
        ))

        # 5. Availabilities
        self.stdout.write("Creating service availabilities...")
        today = timezone.now().date()
        for service in services:
            # Create availability for the next 60 days
            for i in range(60):
                date = today + timedelta(days=i)
                ServiceAvailability.objects.create(
                    service=service,
                    start_date=date,
                    end_date=date,
                    available_quantity=service.capacity,
                )

        # 6. Discounts
        self.stdout.write("Creating discounts...")
        Discount.objects.create(
            vendor=vendor_profiles[0],
            code="WELCOME20",
            name="Welcome Discount",
            description="20% off for first-time bookings at Kigali Luxury",
            discount_type="percentage",
            discount_value=20.00,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

        # 7. Sample Bookings
        self.stdout.write("Creating sample bookings...")
        
        # Booking 1: A complete trip for John Doe
        booking1 = Booking.objects.create(
            user=clients[0],
            total_amount=Decimal("2220.00"),
            currency="USD",
            status="confirmed",
            guest_info={"primary_guest": "John Doe", "total_guests": 2}
        )

        # Hotel Item
        BookingItem.objects.create(
            user=clients[0],
            service=services[0],
            booking=booking1,
            item_type="hotel",
            title=services[0].title,
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=7),
            quantity=1,
            unit_price=services[0].base_price,
            status="booked"
        )

        # Experience Item
        BookingItem.objects.create(
            user=clients[0],
            service=services[2],
            booking=booking1,
            item_type="experience",
            title=services[2].title,
            start_date=today + timedelta(days=6),
            quantity=1,
            unit_price=services[2].base_price,
            status="booked"
        )

        # Booking 2: Pending booking for Jane Smith
        booking2 = Booking.objects.create(
            user=clients[1],
            total_amount=Decimal("120.00"),
            currency="USD",
            status="pending",
            guest_info={"primary_guest": "Jane Smith", "total_guests": 1}
        )

        BookingItem.objects.create(
            user=clients[1],
            service=services[3],
            booking=booking2,
            item_type="tour",
            title=services[3].title,
            start_date=today + timedelta(days=10),
            quantity=1,
            unit_price=services[3].base_price,
            status="draft"
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with realistic data!"))
        self.stdout.write(self.style.WARNING("Access Credentials:"))
        self.stdout.write("  Admin: admin@vizit.africa / password123")
        self.stdout.write("  Client: john.doe@example.com / password123")
        self.stdout.write("  Vendor: stay@kigaliluxury.rw / password123")

