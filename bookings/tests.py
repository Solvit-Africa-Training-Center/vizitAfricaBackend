from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from accounts.models import User
from bookings.models import Booking, BookingItem


class TripLifecycleTest(TestCase):
    """full request -> quote -> accept lifecycle"""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@vizit.com",
            password="admin123",
            full_name="Admin User",
            phone_number="1234567890",
            role="ADMIN",
            is_active=True,
            is_staff=True,
        )

        self.user = User.objects.create_user(
            email="user@test.com",
            password="user123",
            full_name="Test User",
            phone_number="0987654321",
            role="CLIENT",
            is_active=True,
        )

    def _submit_trip(self):
        payload = {
            "departureCity": "Kigali",
            "destination": "Virunga",
            "departureDate": "2026-06-01",
            "returnDate": "2026-06-07",
            "adults": 2,
            "children": 1,
            "infants": 0,
            "name": "Test User",
            "email": self.user.email,
            "phone": "+250780000000",
            "tripPurpose": "leisure",
            "specialRequests": "vegetarian meals",
            "items": [
                {
                    "id": "flight-1",
                    "type": "flight",
                    "title": "Kigali to Goma",
                    "description": "one-way flight",
                    "price": 250,
                    "quantity": 2,
                },
                {
                    "id": "hotel-1",
                    "type": "hotel",
                    "title": "Virunga Lodge",
                    "description": "3 nights",
                    "price": 180,
                    "quantity": 3,
                },
            ],
        }

        self.client.force_authenticate(user=self.user)
        return self.client.post("/api/bookings/submit-trip/", payload, format="json")

    def test_submit_trip_creates_booking(self):
        resp = self._submit_trip()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)

        booking = Booking.objects.first()
        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.user, self.user)

    def test_user_booking_list_returns_full_details(self):
        self._submit_trip()
        resp = self.client.get("/api/bookings/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.json()
        self.assertTrue(len(data) >= 1)

        booking = data[0]
        self.assertEqual(booking["name"], "Test User")
        self.assertEqual(booking["email"], self.user.email)
        self.assertEqual(booking["adults"], 2)
        self.assertEqual(booking["children"], 1)
        self.assertTrue(booking["needsFlights"])
        self.assertTrue(booking["needsHotel"])
        self.assertFalse(booking["needsCar"])
        self.assertEqual(booking["specialRequests"], "vegetarian meals")
        self.assertEqual(booking["status"], "pending")

    def test_user_booking_detail_returns_full_details(self):
        self._submit_trip()
        booking = Booking.objects.first()

        resp = self.client.get(f"/api/bookings/{booking.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.json()
        self.assertEqual(data["name"], "Test User")
        self.assertIn("quote", data)
        self.assertIn("items", data)
        self.assertEqual(data["tripPurpose"], "leisure")

    def test_admin_sends_quote(self):
        self._submit_trip()
        booking = Booking.objects.first()

        self.client.force_authenticate(user=self.admin)
        quote_payload = {
            "items": [
                {
                    "type": "flight",
                    "title": "Kigali to Goma - RwandAir",
                    "description": "round trip economy",
                    "quantity": 2,
                    "unit_price": 320,
                },
                {
                    "type": "hotel",
                    "title": "Virunga Lodge Premium",
                    "description": "3 nights, breakfast included",
                    "quantity": 3,
                    "unit_price": 250,
                },
            ],
            "notes": "best prices available",
            "currency": "USD",
        }

        resp = self.client.post(
            f"/api/bookings/{booking.id}/quote/", quote_payload, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, "quoted")
        self.assertIn("packageQuote", booking.guest_info)

    def test_user_sees_quote_in_booking(self):
        self._submit_trip()
        booking = Booking.objects.first()

        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f"/api/bookings/{booking.id}/quote/",
            {
                "items": [
                    {"type": "flight", "title": "Flight", "quantity": 1, "unit_price": 500}
                ]
            },
            format="json",
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(f"/api/bookings/{booking.id}/")
        data = resp.json()

        self.assertIsNotNone(data["quote"])
        self.assertEqual(data["quote"]["status"], "quoted")
        self.assertEqual(data["status"], "quoted")

    def test_user_accepts_quote(self):
        self._submit_trip()
        booking = Booking.objects.first()

        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f"/api/bookings/{booking.id}/quote/",
            {
                "items": [
                    {"type": "flight", "title": "Flight", "quantity": 2, "unit_price": 300}
                ]
            },
            format="json",
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f"/api/bookings/{booking.id}/accept/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")

        confirmed_items = booking.items.filter(status="booked")
        self.assertTrue(confirmed_items.exists())

    def test_admin_list_returns_requested_items(self):
        self._submit_trip()

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/api/bookings/admin/bookings/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.json()
        booking = data[0]
        self.assertIn("requestedItems", booking)
        self.assertTrue(len(booking["requestedItems"]) > 0)

    def test_non_admin_cannot_send_quote(self):
        self._submit_trip()
        booking = Booking.objects.first()

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            f"/api/bookings/{booking.id}/quote/",
            {"items": [{"type": "flight", "title": "x", "quantity": 1, "unit_price": 100}]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_accept_without_quote(self):
        self._submit_trip()
        booking = Booking.objects.first()

        resp = self.client.post(f"/api/bookings/{booking.id}/accept/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class BookingSerializerTest(TestCase):
    """verify response shape matches frontend contract"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="shape@test.com",
            password="test123",
            full_name="Shape Test",
            phone_number="1234567890",
            role="CLIENT",
            is_active=True,
        )

        self.booking = Booking.objects.create(
            user=self.user,
            total_amount=Decimal("0.00"),
            currency="USD",
            status="pending",
            guest_info={
                "name": "Shape Test",
                "email": "shape@test.com",
                "phone": "+250780111111",
                "departureDate": "2026-07-01",
                "returnDate": "2026-07-05",
                "adults": 1,
                "children": 0,
                "infants": 0,
                "tripPurpose": "business",
                "specialRequests": "late checkout",
                "requestedItems": [
                    {"type": "flight", "title": "Test Flight", "quantity": 1, "price": 500}
                ],
            },
        )

    def test_booking_response_has_all_expected_fields(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get(f"/api/bookings/{self.booking.id}/")

        expected_fields = [
            "id", "name", "email", "phone",
            "arrivalDate", "departureDate",
            "travelers", "adults", "children", "infants",
            "needsFlights", "needsHotel", "needsCar", "needsGuide",
            "status", "currency", "total_amount",
            "specialRequests", "tripPurpose",
            "items", "quote", "createdAt",
        ]

        data = resp.json()
        for field in expected_fields:
            self.assertIn(field, data, f"missing field: {field}")

    def test_guest_info_correctly_extracted(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get(f"/api/bookings/{self.booking.id}/")
        data = resp.json()

        self.assertEqual(data["name"], "Shape Test")
        self.assertEqual(data["phone"], "+250780111111")
        self.assertEqual(data["arrivalDate"], "2026-07-01")
        self.assertEqual(data["departureDate"], "2026-07-05")
        self.assertEqual(data["adults"], 1)
        self.assertEqual(data["travelers"], 1)
        self.assertEqual(data["tripPurpose"], "business")
        self.assertEqual(data["specialRequests"], "late checkout")
        self.assertTrue(data["needsFlights"])
        self.assertFalse(data["needsHotel"])
