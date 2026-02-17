from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from locations.models import Location


class LocationApiTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("location-list")
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pass1234",
            full_name="Location User",
            phone_number="+250788100001",
            role=User.ADMIN,
            is_active=True,
        )

    def test_public_can_list_locations(self):
        Location.objects.create(
            name="Kigali",
            latitude=Decimal("1.944100"),
            longitude=Decimal("30.061900"),
        )

        response = self.client.get(self.list_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Kigali")

    def test_unauthenticated_create_is_denied(self):
        payload = {
            "name": "Nairobi",
            "latitude": "1.292100",
            "longitude": "36.821900",
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_create_is_allowed(self):
        self.client.force_authenticate(self.user)
        payload = {
            "name": "Nairobi",
            "latitude": "1.292100",
            "longitude": "36.821900",
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Location.objects.filter(name="Nairobi").exists())
