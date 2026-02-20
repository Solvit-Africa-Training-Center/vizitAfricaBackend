from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from accounts.models import User
from vendors.models import Vendor
from locations.models import Location
from services.models import Service, ServiceMedia


LOCATIONS = [
    {"name": "Kigali", "lat": -1.9403, "lng": 29.8739},
    {"name": "Volcanoes National Park", "lat": -1.4833, "lng": 29.5333},
    {"name": "Akagera National Park", "lat": -1.8833, "lng": 30.7167},
    {"name": "Nyungwe Forest", "lat": -2.4833, "lng": 29.2167},
    {"name": "Lake Kivu", "lat": -2.0667, "lng": 29.2500},
    {"name": "Musanze", "lat": -1.5000, "lng": 29.6333},
    {"name": "Gisenyi", "lat": -1.7000, "lng": 29.2500},
    {"name": "Huye", "lat": -2.6000, "lng": 29.7333},
]

# Define vendors to be created/retrieved
VENDORS_DATA = {
    "heaven": {
        "email": "vendor@heavenrwanda.com",
        "name": "Heaven Rwanda",
        "phone": "+250780000002",
        "business_name": "Heaven Rwanda",
        "type": "hotel_chain"
    },
    "rwandair": {
        "email": "vendor@rwandair.com",
        "name": "RwandAir Admin",
        "phone": "+250780000003",
        "business_name": "RwandAir",
        "type": "airline"
    },
    "volcanoes": {
        "email": "vendor@volcanoes.com",
        "name": "Volcanoes Safaris",
        "phone": "+250780000004",
        "business_name": "Volcanoes Safaris",
        "type": "tour_operator"
    },
    "vizit": {
        "email": "vendor@vizit.com",
        "name": "Vizit Vendor",
        "phone": "+250780000005",
        "business_name": "Vizit Africa",
        "type": "tour_operator"
    }
}

CLIENTS_DATA = [
    {"email": "alice@example.com", "name": "Alice Traveler", "phone": "+250780000100"},
    {"email": "bob@example.com", "name": "Bob Explorer", "phone": "+250780000101"},
]

SERVICES = [
    # hotels
    {
        "external_id": "ht-1",
        "vendor_key": "heaven",
        "title": "The Retreat by Heaven",
        "service_type": "hotel",
        "description": "A luxury boutique hotel nestled in the hills of Kigali with panoramic city views, infinity pool, and farm-to-table dining. Perfect for travelers seeking tranquility and world-class hospitality in the heart of Rwanda.",
        "base_price": Decimal("450.00"),
        "capacity": 24,
        "location_name": "Kigali",
        "metadata": {"stars": 5, "amenities": ["pool", "spa", "restaurant", "gym", "wifi"], "check_in": "14:00", "check_out": "11:00"},
        "images": ["/images/hotel.jpg"],
    },
    {
        "external_id": "ht-2",
        "vendor_key": "heaven", # Assumption: Heaven manages/partners
        "title": "One&Only Nyungwe House",
        "service_type": "hotel",
        "description": "An exclusive tea plantation lodge on the edge of Nyungwe Forest. Wake to misty mountain views, enjoy guided forest walks, and unwind in elegant suites surrounded by Rwanda's pristine rainforest canopy.",
        "base_price": Decimal("3500.00"),
        "capacity": 16,
        "location_name": "Nyungwe Forest",
        "metadata": {"stars": 5, "amenities": ["spa", "restaurant", "guided_walks", "tea_tasting", "wifi"], "check_in": "15:00", "check_out": "11:00"},
        "images": ["/images/bed-in-hotel-with-yellowish-lightings.jpg"],
    },
    {
        "external_id": "ht-3",
        "vendor_key": "vizit",
        "title": "Lake Kivu Serena Hotel",
        "service_type": "hotel",
        "description": "A lakefront resort offering stunning sunset views over Lake Kivu, water sports, and refined dining. The perfect escape for couples and families looking for relaxation by one of Africa's Great Lakes.",
        "base_price": Decimal("280.00"),
        "capacity": 60,
        "location_name": "Gisenyi",
        "metadata": {"stars": 4, "amenities": ["pool", "beach", "restaurant", "water_sports", "wifi"], "check_in": "14:00", "check_out": "10:00"},
        "images": ["/images/lake-kivu-sunset.jpg"],
    },

    # bnbs
    {
        "external_id": "bnb-1",
        "vendor_key": "vizit",
        "title": "Kigali Soul BnB",
        "service_type": "bnb",
        "description": "A charming guesthouse in Kigali's Kimihurura neighborhood with locally roasted coffee service, curated art, and hosts who share the city's best-kept secrets. Authentic Rwandan warmth meets modern comfort.",
        "base_price": Decimal("80.00"),
        "capacity": 8,
        "location_name": "Kigali",
        "metadata": {"rooms": 4, "amenities": ["breakfast", "coffee_bar", "garden", "wifi"], "style": "boutique"},
        "images": ["/images/coffee.jpg"],
    },
    {
        "external_id": "bnb-2",
        "vendor_key": "vizit",
        "title": "Lavender Home Musanze",
        "service_type": "bnb",
        "description": "A peaceful family-run guesthouse at the foot of the Virunga volcanoes. Ideal base for gorilla trekking with homemade meals, warm hospitality, and spectacular mountain views from every room.",
        "base_price": Decimal("65.00"),
        "capacity": 6,
        "location_name": "Musanze",
        "metadata": {"rooms": 3, "amenities": ["breakfast", "garden", "volcano_views", "wifi"], "style": "family"},
        "images": ["/images/agaseke-black-white.jpg"],
    },

    # car rentals
    {
        "external_id": "car-1",
        "vendor_key": "vizit",
        "title": "Land Cruiser V8 Safari Edition",
        "service_type": "car_rental",
        "description": "The ultimate safari vehicle — a Toyota Land Cruiser V8 with pop-up roof, 4WD, and experienced driver. Built for Rwanda's national parks and unpaved roads. Includes fuel, insurance, and unlimited mileage.",
        "base_price": Decimal("150.00"),
        "capacity": 7,
        "location_name": "Kigali",
        "metadata": {"vehicle": "Toyota Land Cruiser V8", "transmission": "automatic", "fuel": "diesel", "includes": ["driver", "fuel", "insurance"]},
        "images": ["/images/tourism-guide-vehicle-car.jpg"],
    },
    {
        "external_id": "car-2",
        "vendor_key": "vizit",
        "title": "RAV4 City & Country",
        "service_type": "car_rental",
        "description": "A versatile Toyota RAV4 perfect for both Kigali city driving and upcountry adventures. Self-drive or with driver, GPS-equipped, comprehensive insurance included.",
        "base_price": Decimal("80.00"),
        "capacity": 5,
        "location_name": "Kigali",
        "metadata": {"vehicle": "Toyota RAV4", "transmission": "automatic", "fuel": "petrol", "includes": ["GPS", "insurance"]},
        "images": ["/images/road-through-hill.jpg"],
    },
    {
        "external_id": "car-3",
        "vendor_key": "vizit",
        "title": "Mercedes Sprinter Group Van",
        "service_type": "car_rental",
        "description": "Comfortable 12-seater van ideal for group tours, airport transfers, and multi-day itineraries. Professional driver, air conditioning, and large luggage capacity.",
        "base_price": Decimal("200.00"),
        "capacity": 12,
        "location_name": "Kigali",
        "metadata": {"vehicle": "Mercedes Sprinter", "transmission": "manual", "fuel": "diesel", "includes": ["driver", "fuel", "insurance"]},
        "images": ["/images/rwanda-sky-scrapers.jpg"],
    },

    # guides
    {
        "external_id": "gd-1",
        "vendor_key": "volcanoes",
        "title": "Alex — Wildlife & Safari Guide",
        "service_type": "guide",
        "description": "Certified wildlife guide with 10+ years of experience in Akagera and Volcanoes National Parks. Specializes in gorilla trekking preparation, big-five safaris, and birdwatching expeditions.",
        "base_price": Decimal("100.00"),
        "capacity": 8,
        "location_name": "Kigali",
        "metadata": {"languages": ["English", "French", "Kinyarwanda"], "specialties": ["wildlife", "gorilla_trekking", "birding"], "years_experience": 10},
        "images": ["/images/guide.jpg"],
    },
    {
        "external_id": "gd-2",
        "vendor_key": "vizit",
        "title": "Sarah — Culture & Heritage Guide",
        "service_type": "guide",
        "description": "Passionate cultural guide specializing in Kigali's history, art scene, and rural community visits. From genocide memorials to artisan workshops, Sarah connects visitors with Rwanda's living story.",
        "base_price": Decimal("120.00"),
        "capacity": 6,
        "location_name": "Kigali",
        "metadata": {"languages": ["English", "French", "Kinyarwanda", "Swahili"], "specialties": ["culture", "history", "art", "community"], "years_experience": 7},
        "images": ["/images/woman-tailoring.jpg"],
    },

    # experiences
    {
        "external_id": "exp-1",
        "vendor_key": "volcanoes",
        "title": "Gorilla Trekking Expedition",
        "service_type": "experience",
        "description": "Trek through the misty bamboo forests of Volcanoes National Park to encounter endangered mountain gorillas in their natural habitat. A once-in-a-lifetime wildlife encounter guided by expert trackers.",
        "base_price": Decimal("1500.00"),
        "capacity": 8,
        "location_name": "Volcanoes National Park",
        "metadata": {"category": "wildlife", "duration": "Full day", "difficulty": "moderate", "tags": ["Adventure", "Wildlife", "Physical"]},
        "images": ["/images/wildlife-silverback-gorilla.jpg"],
    },
    {
        "external_id": "exp-2",
        "vendor_key": "vizit",
        "title": "Akagera Big Five Safari",
        "service_type": "experience",
        "description": "A full-day game drive through Akagera National Park — Rwanda's only savannah park. Spot lions, elephants, giraffes, hippos, and over 500 bird species across stunning lakeside landscapes.",
        "base_price": Decimal("450.00"),
        "capacity": 7,
        "location_name": "Akagera National Park",
        "metadata": {"category": "wildlife", "duration": "Full day", "difficulty": "easy", "tags": ["Wildlife", "Safari", "Nature"]},
        "images": ["/images/wildlife-ankole-cow.jpg"],
    },
    {
        "external_id": "exp-3",
        "vendor_key": "heaven",
        "title": "Nyungwe Canopy Walkway",
        "service_type": "experience",
        "description": "Walk suspended 50 meters above the ancient Nyungwe rainforest floor on East Africa's only canopy walkway. Spot chimpanzees, colobus monkeys, and rare orchids in one of Africa's oldest forests.",
        "base_price": Decimal("200.00"),
        "capacity": 10,
        "location_name": "Nyungwe Forest",
        "metadata": {"category": "wildlife", "duration": "Half day", "difficulty": "moderate", "tags": ["Adventure", "Nature", "Hiking"]},
        "images": ["/images/rwanda-walk-path-in-forest.jpg"],
    },
    {
        "external_id": "exp-4",
        "vendor_key": "vizit",
        "title": "Kigali City & Genocide Memorial Tour",
        "service_type": "experience",
        "description": "Discover Kigali's transformation from its moving Genocide Memorial to its vibrant art galleries, bustling markets, and world-class restaurants. A journey through Rwanda's resilience and innovation.",
        "base_price": Decimal("80.00"),
        "capacity": 12,
        "location_name": "Kigali",
        "metadata": {"category": "culture", "duration": "Half day", "difficulty": "easy", "tags": ["Culture", "History", "Urban"]},
        "images": ["/images/city-kigali-roundabout-with-woman-and-child-statue.jpg"],
    },
    {
        "external_id": "exp-5",
        "vendor_key": "vizit",
        "title": "Lake Kivu Relaxation Retreat",
        "service_type": "experience",
        "description": "Unwind on the shores of Lake Kivu with kayaking, island hopping, traditional fishing, and sunset boat cruises. Combine adventure with relaxation on one of Africa's Great Lakes.",
        "base_price": Decimal("350.00"),
        "capacity": 8,
        "location_name": "Lake Kivu",
        "metadata": {"category": "culture", "duration": "2-3 days", "difficulty": "easy", "tags": ["Relaxation", "Water", "Leisure"]},
        "images": ["/images/kivu-grass-seats.jpg"],
    },
    {
        "external_id": "exp-6",
        "vendor_key": "volcanoes",
        "title": "Mount Bisoke Volcano Hike",
        "service_type": "experience",
        "description": "Summit the 3,711m Bisoke volcano and gaze into its stunning crater lake. A challenging but rewarding hike through bamboo forest and alpine meadows with panoramic views of the Virunga chain.",
        "base_price": Decimal("75.00"),
        "capacity": 10,
        "location_name": "Volcanoes National Park",
        "metadata": {"category": "adventure", "duration": "Full day", "difficulty": "challenging", "tags": ["Hiking", "Adventure", "Physical"]},
        "images": ["/images/a-hill.jpg"],
    },

    # flights
    {
        "external_id": "fl-1",
        "vendor_key": "rwandair",
        "title": "Kigali — Nairobi (RwandAir)",
        "service_type": "flight",
        "description": "Direct flight from Kigali International Airport to Jomo Kenyatta International Airport. RwandAir's premium economy with complimentary meals and 23kg baggage.",
        "base_price": Decimal("320.00"),
        "capacity": 150,
        "location_name": "Kigali",
        "metadata": {"airline": "RwandAir", "route": "KGL-NBO", "duration": "1h 30m", "class": "economy", "departure_time": "08:00", "arrival_time": "09:30"},
        "images": ["/images/person-waiting-at-airport.jpg"],
    },
    {
        "external_id": "fl-2",
        "vendor_key": "rwandair",
        "title": "Kigali — Dubai (RwandAir)",
        "service_type": "flight",
        "description": "Non-stop service from Kigali to Dubai International Airport. RwandAir's flagship route with full meal service, in-flight entertainment, and 30kg checked baggage.",
        "base_price": Decimal("650.00"),
        "capacity": 200,
        "location_name": "Kigali",
        "metadata": {"airline": "RwandAir", "route": "KGL-DXB", "duration": "6h 15m", "class": "economy", "departure_time": "22:00", "arrival_time": "06:15"},
        "images": ["/images/person-waiting-at-airport.jpg"],
    },
    {
        "external_id": "fl-3",
        "vendor_key": "rwandair",
        "title": "Kigali — Brussels (Brussels Airlines)",
        "service_type": "flight",
        "description": "Direct overnight flight from Kigali to Brussels Airport. Brussels Airlines economy with meal service, personal entertainment, and convenient morning arrival in Europe.",
        "base_price": Decimal("780.00"),
        "capacity": 250,
        "location_name": "Kigali",
        "metadata": {"airline": "Brussels Airlines", "route": "KGL-BRU", "duration": "9h 30m", "class": "economy", "departure_time": "23:30", "arrival_time": "06:00"},
        "images": ["/images/person-waiting-at-airport.jpg"],
    },
    {
        "external_id": "fl-4",
        "vendor_key": "vizit", # Partner airline via Vizit
        "title": "Kigali — Addis Ababa (Ethiopian Airlines)",
        "service_type": "flight",
        "description": "Connecting flight via Addis Ababa Bole International Airport. Ethiopian Airlines Star Alliance service with access to the largest African hub and onward connections worldwide.",
        "base_price": Decimal("280.00"),
        "capacity": 180,
        "location_name": "Kigali",
        "metadata": {"airline": "Ethiopian Airlines", "route": "KGL-ADD", "duration": "2h 10m", "class": "economy", "departure_time": "14:00", "arrival_time": "16:10"},
        "images": ["/images/person-waiting-at-airport.jpg"],
    },
]


class Command(BaseCommand):
    help = "Seed locations, services, users, and vendors for development"

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Admin
        admin = self._ensure_admin()
        
        # 2. Clients
        self._seed_clients()

        # 3. Vendors
        vendors_map = self._seed_vendors(admin)

        # 4. Locations
        locations_map = self._seed_locations()

        # 5. Services
        created, skipped = self._seed_services(vendors_map, locations_map)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"done — {created} services created, {skipped} skipped."
        ))

    def _ensure_admin(self):
        admin, created = User.objects.get_or_create(
            email="admin@vizitafrica.com",
            defaults={
                "full_name": "Vizit Admin",
                "phone_number": "+250780000001",
                "role": "ADMIN",
                "is_active": True,
                "is_staff": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(f"  created admin user: {admin.email} (pw: admin123)")
        return admin

    def _seed_clients(self):
        for client_data in CLIENTS_DATA:
            user, created = User.objects.get_or_create(
                email=client_data["email"],
                defaults={
                    "full_name": client_data["name"],
                    "phone_number": client_data["phone"],
                    "role": "CLIENT",
                    "is_active": True,
                }
            )
            if created:
                user.set_password("client123")
                user.save()
                self.stdout.write(f"  created client: {user.email} (pw: client123)")

    def _seed_vendors(self, admin):
        vendors_map = {}
        
        for key, data in VENDORS_DATA.items():
            # Create/Get User for Vendor
            user, u_created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "full_name": data["name"],
                    "phone_number": data["phone"],
                    "role": "VENDOR",
                    "is_active": True,
                }
            )
            if u_created:
                user.set_password("vendor123")
                user.save()

            # Create/Get Vendor Profile
            vendor, v_created = Vendor.objects.get_or_create(
                user=user,
                defaults={
                    "business_name": data["business_name"],
                    "vendor_type": data["type"],
                    "is_approved": True,
                    "approved_by": admin,
                },
            )
            
            vendors_map[key] = vendor
            if u_created or v_created:
                 self.stdout.write(f"  created vendor: {vendor.business_name} ({user.email})")
        
        return vendors_map

    def _seed_locations(self):
        result = {}
        for loc in LOCATIONS:
            obj, created = Location.objects.get_or_create(
                name=loc["name"],
                defaults={"latitude": loc["lat"], "longitude": loc["lng"]},
            )
            result[loc["name"]] = obj
            if created:
                self.stdout.write(f"  + location: {obj.name}")
        return result

    def _seed_services(self, vendors_map, locations_map):
        created_count = 0
        skipped_count = 0

        for svc in SERVICES:
            vendor = vendors_map.get(svc["vendor_key"])
            location = locations_map.get(svc["location_name"])
            
            if not vendor or not location:
                self.stdout.write(self.style.WARNING(f"  Skipping {svc['title']} - missing vendor/location"))
                continue

            if Service.objects.filter(external_id=svc["external_id"]).exists():
                # Update existing service vendor
                s = Service.objects.get(external_id=svc["external_id"])
                if s.user != vendor.user:
                    s.user = vendor.user
                    s.save()
                    self.stdout.write(f"  ~ updated owner: {svc['title']} -> {vendor.business_name}")
                else:
                    skipped_count += 1
                continue

            service = Service.objects.create(
                user=vendor.user,
                location=location,
                title=svc["title"],
                service_type=svc["service_type"],
                description=svc["description"],
                base_price=svc["base_price"],
                currency="USD",
                capacity=svc["capacity"],
                status="active",
                external_id=svc["external_id"],
                metadata=svc.get("metadata", {}),
            )

            for i, img in enumerate(svc.get("images", [])):
                ServiceMedia.objects.create(
                    service=service,
                    media_url=img,
                    media_type="image",
                    sort_order=i,
                )

            created_count += 1
            self.stdout.write(f"  + {svc['service_type']}: {svc['title']} (by {vendor.business_name})")

        return created_count, skipped_count
