from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from accounts.models import User
from bookings.models import Booking, BookingItem
from services.models import Service
from locations.models import Location


class TripLifecycleTest(TestCase):
    # test relational trip lifecycle

    def setUp(self):
        self.client = APIClient()

        # admin
        self.admin = User.objects.create_user(
            email="admin@vizit.com",
            password="admin123",
            full_name="Admin User",
            phone_number="1234567890",
            role="ADMIN",
            is_active=True,
            is_staff=True,
        )

        # client
        self.user = User.objects.create_user(
            email="user@test.com",
            password="user123",
            full_name="Test User",
            phone_number="0987654321",
            role="CLIENT",
            is_active=True,
        )

        # service
        loc = Location.objects.create(name="Kigali", latitude=0, longitude=0)
        self.service = Service.objects.create(
            user=self.admin, 
            location=loc,
            title="Luxury Safari",
            service_type="experience",
            base_price=Decimal("500.00"),
            capacity=10,
            external_id="exp-100"
        )

    def test_guest_submission_forces_zero_price(self):
        # guests cannot set prices
        payload = {
            "name": "Guest User",
            "email": "guest@test.com",
            "phone_number": "555-0123",
            "departure_city": "London",
            "arrival_date": "2026-10-01",
            "departure_date": "2026-10-10",
            "adults": 2,
            "items": [
                {
                    "type": "custom",
                    "title": "Private Boat",
                    "unit_price": 9999.00,
                    "quantity": 1
                }
            ]
        }
        
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/bookings/submit-trip/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        
        booking = Booking.objects.get(departure_city="London")
        item = booking.items.first()
        
        self.assertEqual(item.unit_price, Decimal("0.00"))
        self.assertEqual(booking.total_amount, Decimal("0.00"))

    def test_with_driver_and_round_trip_columns(self):
        # verify promoted fields store in columns
        payload = {
            "name": "Driver Test",
            "email": "driver@test.com",
            "phone_number": "12345",
            "departure_city": "Paris",
            "arrival_date": "2026-10-01",
            "departure_date": "2026-10-10",
            "items": [
                {
                    "type": "car",
                    "title": "SUV",
                    "with_driver": True,
                    "is_round_trip": True,
                    "return_date": "2026-10-10",
                    "quantity": 1
                }
            ]
        }
        
        self.client.force_authenticate(user=None)
        self.client.post("/api/bookings/submit-trip/", payload, format="json")
        item = BookingItem.objects.get(title="SUV")
        
        self.assertTrue(item.with_driver)
        self.assertTrue(item.is_round_trip)
        self.assertEqual(str(item.return_date), "2026-10-10")

    def test_admin_quote_updates_relational_items(self):
        # admin can update prices
        self.client.force_authenticate(user=self.user)
        resp = self.client.post("/api/bookings/submit-trip/", {
            "name": "Quote Test",
            "email": self.user.email,
            "phone_number": "123456",
            "departure_city": "NYC",
            "arrival_date": "2026-11-01",
            "departure_date": "2026-11-05",
            "items": [{"type": "experience", "title": "Old Title", "quantity": 1}]
        }, format="json")
        
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        
        booking = Booking.objects.get(departure_city="NYC")
        initial_item = booking.items.first()

        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f"/api/bookings/{booking.id}/quote/", {
            "items": [
                {
                    "id": str(initial_item.id),
                    "title": "Updated Luxury Safari",
                    "unit_price": 450.00,
                    "quantity": 2,
                    "start_date": "2026-11-01",
                    "end_date": "2026-11-05"
                }
            ]
        }, format="json")
        
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        booking.refresh_from_db()
        item = booking.items.first()
        
        self.assertEqual(booking.status, Booking.Status.QUOTED)
        self.assertEqual(item.title, "Updated Luxury Safari")
        self.assertEqual(item.unit_price, Decimal("450.00"))
        self.assertEqual(booking.total_amount, Decimal("900.00"))

    def test_accept_quote_updates_status_and_items(self):
        # acceptance flow
        booking = Booking.objects.create(
            user=self.user, 
            status=Booking.Status.QUOTED, 
            total_amount=Decimal("100.00"),
            arrival_date="2026-12-01"
        )
        item = BookingItem.objects.create(
            booking=booking, 
            user=self.user,
            title="Test Item", 
            quantity=1, 
            unit_price=Decimal("100.00"),
            subtotal=Decimal("100.00"),
            status=BookingItem.Status.RESERVED
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f"/api/bookings/{booking.id}/accept/", {}, format="json")
        
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        booking.refresh_from_db()
        item.refresh_from_db()
        
        self.assertEqual(booking.status, Booking.Status.ACCEPTED)
        self.assertEqual(item.status, BookingItem.Status.BOOKED)
        self.assertIsNotNone(booking.quote_accepted_at)

    def test_strict_snake_case_consistency(self):
        # verify snake_case response
        booking = Booking.objects.create(
            user=self.user,
            departure_city="Berlin",
            arrival_date="2026-05-01",
            needs_flights=True
        )
        
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(f"/api/bookings/{booking.id}/")
        
        data = resp.json()
        self.assertIn("arrival_date", data)
        self.assertIn("needs_flights", data)
        self.assertNotIn("arrivalDate", data)
        
    def test_limit_of_pending_requests(self):
        # limit spam
        for i in range(2):
            Booking.objects.create(user=self.user, status=Booking.Status.PENDING)
            
        payload = {
            "name": "Spam Test",
            "email": self.user.email,
            "phone_number": "999",
            "departure_city": "SpamCity",
            "arrival_date": "2026-01-01",
            "departure_date": "2026-01-05",
            "items": [{"type": "service", "title": "Spam", "quantity": 1}]
        }
        
        self.client.force_authenticate(user=self.user)
        resp = self.client.post("/api/bookings/submit-trip/", payload, format="json")
        
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
        body = resp.json()
        error_msg = body.get("message") or body.get("error", {}).get("message", "")
        self.assertIn("limit", str(error_msg).lower())
