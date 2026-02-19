import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from accounts.models import User
from vendors.models import Vendor
from locations.models import Location
from services.models import Service, ServiceMedia, ServiceAvailability, Discount
from bookings.models import Booking, BookingItem
from transactions.models import Transaction
from payments.models import Payment
from tickets.models import Ticket
from decimal import Decimal
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = "Seed the database with initial data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting existing data...")
        
        # Order of deletion matters due to foreign key constraints if not using CASCADE
        # but Django's delete() handles most of it.
        Ticket.objects.all().delete()
        Payment.objects.all().delete()
        Transaction.objects.all().delete()
        BookingItem.objects.all().delete()
        Booking.objects.all().delete()
        ServiceAvailability.objects.all().delete()
        ServiceMedia.objects.all().delete()
        Service.objects.all().delete()
        Vendor.objects.all().delete()
        Location.objects.all().delete()
        
        # Delete all users except possibly keeping the admin if preferred, 
        # but for a full reset we delete all and recreate.
        User.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS("Existing data deleted."))
        self.stdout.write("Seeding data...")

        # 1. Create Admin
        admin_email = "admin@vizitafrica.com"
        if not User.objects.filter(email=admin_email).exists():
            admin = User.objects.create_superuser(
                email=admin_email,
                password="adminpassword",
                full_name="Admin User",
                phone_number="+250780000000"
            )
            admin.is_active = True
            admin.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin: {admin_email}"))
        else:
            admin = User.objects.get(email=admin_email)

        # 2. Create Locations
        locations_data = [
            {"name": "Kigali, Rwanda", "latitude": -1.9441, "longitude": 30.0619},
            {"name": "Musanze, Rwanda", "latitude": -1.4998, "longitude": 29.6349},
            {"name": "Nairobi, Kenya", "latitude": -1.2921, "longitude": 36.8219},
            {"name": "Mombasa, Kenya", "latitude": -4.0435, "longitude": 39.6682},
            {"name": "Dar es Salaam, Tanzania", "latitude": -6.7924, "longitude": 39.2083},
        ]
        
        locations = []
        for loc_data in locations_data:
            loc, created = Location.objects.get_or_create(
                name=loc_data["name"],
                defaults={"latitude": loc_data["latitude"], "longitude": loc_data["longitude"]}
            )
            locations.append(loc)
            if created:
                self.stdout.write(f"Created location: {loc.name}")

        # 3. Create Vendors
        vendor_types = ["Tour Operator", "Hotel", "Car Rental", "Restaurant"]
        vendors = []
        for i in range(1, 5):
            email = f"vendor{i}@example.com"
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    email=email,
                    password="password123",
                    full_name=f"Vendor User {i}",
                    phone_number=f"+25078000000{i}",
                    role=User.VENDOR,
                    is_active=True
                )
                vendor = Vendor.objects.create(
                    user=user,
                    business_name=f"Africa Adventures {i}",
                    vendor_type=random.choice(vendor_types),
                    is_approved=True,
                    approved_by=admin,
                    approved_on=timezone.now()
                )
                vendors.append(vendor)
                self.stdout.write(f"Created vendor: {vendor.business_name}")
            else:
                vendors.append(Vendor.objects.get(user__email=email))

        # 4. Create Services
        service_types = ["City Tour", "Mountain Gorilla Trekking", "Safari", "Beach Holiday"]
        services = []
        for i in range(1, 11):
            vendor = random.choice(vendors)
            location = random.choice(locations)
            service = Service.objects.create(
                user=vendor.user,
                location=location,
                title=f"Amazing {random.choice(service_types)} {i}",
                service_type="Activity",
                description=f"Experience the beauty of Africa with our special {i} tour.",
                base_price=Decimal(random.randint(50, 500)),
                currency="USD",
                capacity=random.randint(2, 20),
                status="active",
                metadata={"duration": "4 hours", "difficulty": "Easy"}
            )
            services.append(service)
            
            # Add Media
            ServiceMedia.objects.create(
                service=service,
                media_url=f"https://picsum.photos/seed/{service.id}/800/600",
                media_type="image",
                sort_order=0
            )

            # Add Availability
            ServiceAvailability.objects.create(
                service=service,
                start_date=timezone.now().date(),
                end_date=(timezone.now() + datetime.timedelta(days=30)).date(),
                available_quantity=service.capacity
            )
            
            self.stdout.write(f"Created service: {service.title}")

        # 5. Create Clients
        clients = []
        for i in range(1, 4):
            email = f"client{i}@example.com"
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    email=email,
                    password="password123",
                    full_name=f"Client User {i}",
                    phone_number=f"+25078100000{i}",
                    role=User.CLIENT,
                    is_active=True
                )
                clients.append(user)
                self.stdout.write(f"Created client: {user.email}")
            else:
                clients.append(User.objects.get(email=email))

        # 6. Create Bookings, Payments, Tickets, and Transactions
        for i in range(1, 6):
            client = random.choice(clients)
            service = random.choice(services)
            
            booking = Booking.objects.create(
                user=client,
                total_amount=service.base_price,
                currency="USD",
                status="confirmed",
                guest_info={"primary_guest": client.full_name}
            )
            
            BookingItem.objects.create(
                user=client,
                service=service,
                booking=booking,
                item_type="service",
                title=service.title,
                quantity=1,
                unit_price=service.base_price,
                subtotal=service.base_price,
                status="booked"
            )

            payment = Payment.objects.create(
                booking=booking,
                user=client,
                amount=service.base_price,
                currency="USD",
                status="succeeded",
                payment_method="Mobile Money",
                transaction_id=f"TXN-{random.randint(10000, 99999)}"
            )

            Ticket.objects.create(
                booking=booking,
                payment=payment,
                pdf_url=f"https://example.com/tickets/{booking.id}.pdf",
                qr_code_data=f"TICKET-{booking.id}",
                expires_at=timezone.now() + datetime.timedelta(days=7)
            )
            
            Transaction.objects.create(
                booking=booking,
                user=client,
                amount=service.base_price,
                currency="USD",
                transaction_type="payout",
                status="completed"
            )
            
            self.stdout.write(f"Created booking, payment, and ticket for {client.email}")

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

