from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from bookings.models import Booking, BookingItem
from locations.models import Location
from services.models import Service


class BookingQuoteApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.quote@example.com",
            password="pass1234",
            full_name="Quote Admin",
            phone_number="+250788200001",
            role=User.ADMIN,
            is_active=True,
        )
        self.client_user = User.objects.create_user(
            email="client.quote@example.com",
            password="pass1234",
            full_name="Quote Client",
            phone_number="+250788200002",
            role=User.CLIENT,
            is_active=True,
        )
        self.other_client = User.objects.create_user(
            email="other.quote@example.com",
            password="pass1234",
            full_name="Other Client",
            phone_number="+250788200003",
            role=User.CLIENT,
            is_active=True,
        )

        self.location = Location.objects.create(
            name="Kigali",
            latitude=Decimal("1.944100"),
            longitude=Decimal("30.061900"),
        )
        self.service = Service.objects.create(
            user=self.admin,
            location=self.location,
            title="RwandAir Direct",
            service_type="flight",
            description="Direct and comfortable route.",
            base_price=Decimal("500.00"),
            currency="USD",
            capacity=120,
            status="active",
            external_id="fl-500",
        )

        self.booking = Booking.objects.create(
            user=self.client_user,
            total_amount=Decimal("0.00"),
            currency="USD",
            status="pending",
            guest_info={
                "name": "Quote Client",
                "email": "client.quote@example.com",
                "departureDate": "2026-05-01",
                "returnDate": "2026-05-06",
            },
        )

    def _send_quote_url(self, booking_id):
        return reverse("admin-booking-send-quote", kwargs={"booking_id": booking_id})

    def _accept_quote_url(self, booking_id):
        return reverse("booking-accept-quote", kwargs={"booking_id": booking_id})

    def test_admin_can_send_quote_and_booking_is_updated(self):
        self.client.force_authenticate(self.admin)
        payload = {
            "currency": "USD",
            "notes": "Special admin quote",
            "items": [
                {
                    "id": "fl-500",
                    "service": "fl-500",
                    "type": "flight",
                    "title": "RwandAir Direct",
                    "description": "Morning departure",
                    "quantity": 2,
                    "unit_price": "600.00",
                }
            ],
        }

        response = self.client.post(
            self._send_quote_url(self.booking.id),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "quoted")
        self.assertEqual(self.booking.total_amount, Decimal("1200.00"))
        quote = self.booking.guest_info.get("packageQuote")
        self.assertIsInstance(quote, dict)
        self.assertEqual(quote.get("status"), "quoted")
        self.assertEqual(quote.get("currency"), "USD")
        self.assertEqual(len(quote.get("items", [])), 1)

    def test_non_admin_cannot_send_quote(self):
        self.client.force_authenticate(self.client_user)
        payload = {
            "items": [
                {
                    "title": "RwandAir Direct",
                    "type": "flight",
                    "quantity": 1,
                    "unit_price": "500.00",
                }
            ]
        }

        response = self.client.post(
            self._send_quote_url(self.booking.id),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_quote_requires_items(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self._send_quote_url(self.booking.id),
            {"items": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_client_can_accept_quote_and_booking_becomes_confirmed(self):
        self.booking.guest_info["packageQuote"] = {
            "status": "quoted",
            "currency": "USD",
            "total_amount": 700.0,
            "items": [
                {
                    "service": "fl-500",
                    "id": "fl-500",
                    "type": "flight",
                    "title": "RwandAir Direct",
                    "quantity": 1,
                    "unit_price": 700.0,
                }
            ],
        }
        self.booking.status = "quoted"
        self.booking.save(update_fields=["guest_info", "status", "updated_at"])

        self.client.force_authenticate(self.client_user)
        response = self.client.post(self._accept_quote_url(self.booking.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "confirmed")
        self.assertEqual(self.booking.total_amount, Decimal("700.0"))
        quote = self.booking.guest_info.get("packageQuote")
        self.assertEqual(quote.get("status"), "accepted")

        # Accept flow should materialize BookingItem rows if missing.
        self.assertEqual(BookingItem.objects.filter(booking=self.booking).count(), 1)
        created_item = BookingItem.objects.get(booking=self.booking)
        self.assertEqual(created_item.service_id, self.service.id)
        self.assertEqual(created_item.status, "booked")

    def test_accept_quote_requires_owner(self):
        self.booking.guest_info["packageQuote"] = {"status": "quoted", "items": []}
        self.booking.status = "quoted"
        self.booking.save(update_fields=["guest_info", "status", "updated_at"])

        self.client.force_authenticate(self.other_client)
        response = self.client.post(self._accept_quote_url(self.booking.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accept_quote_fails_when_missing_quote(self):
        self.client.force_authenticate(self.client_user)
        response = self.client.post(self._accept_quote_url(self.booking.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_accept_quote_fails_for_invalid_quote_status(self):
        self.booking.guest_info["packageQuote"] = {"status": "accepted", "items": []}
        self.booking.status = "quoted"
        self.booking.save(update_fields=["guest_info", "status", "updated_at"])

        self.client.force_authenticate(self.client_user)
        response = self.client.post(self._accept_quote_url(self.booking.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
