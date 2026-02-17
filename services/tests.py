from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from locations.models import Location
from services.models import Service
from vendors.models import Vendor


class ServiceApiTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("service-list")
        self.location = Location.objects.create(
            name="Kigali",
            latitude=Decimal("1.944100"),
            longitude=Decimal("30.061900"),
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="pass1234",
            full_name="Admin User",
            phone_number="+250788000001",
            role=User.ADMIN,
            is_active=True,
        )
        self.vendor_user = User.objects.create_user(
            email="vendor@example.com",
            password="pass1234",
            full_name="Approved Vendor",
            phone_number="+250788000002",
            role=User.VENDOR,
            is_active=True,
        )
        self.unapproved_vendor_user = User.objects.create_user(
            email="vendor2@example.com",
            password="pass1234",
            full_name="Unapproved Vendor",
            phone_number="+250788000003",
            role=User.VENDOR,
            is_active=True,
        )
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="pass1234",
            full_name="Client User",
            phone_number="+250788000004",
            role=User.CLIENT,
            is_active=True,
        )

        Vendor.objects.create(
            user=self.vendor_user,
            business_name="Approved Vendor Ltd",
            vendor_type="tour_operator",
            is_approved=True,
        )
        Vendor.objects.create(
            user=self.unapproved_vendor_user,
            business_name="Unapproved Vendor Ltd",
            vendor_type="tour_operator",
            is_approved=False,
        )

    def _payload(self, **overrides):
        data = {
            "title": "Kenya Airways",
            "service_type": "flight",
            "description": "Direct route with reliable service and baggage included.",
            "base_price": "2000.00",
            "currency": "USD",
            "capacity": 100,
            "status": "draft",
            "location": self.location.id,
        }
        data.update(overrides)
        return data

    def test_public_list_returns_only_active_services(self):
        Service.objects.create(
            user=self.admin,
            location=self.location,
            title="Active Flight",
            service_type="flight",
            description="Active item",
            base_price=Decimal("100.00"),
            currency="USD",
            capacity=10,
            status="active",
        )
        Service.objects.create(
            user=self.admin,
            location=self.location,
            title="Draft Flight",
            service_type="flight",
            description="Draft item",
            base_price=Decimal("200.00"),
            currency="USD",
            capacity=10,
            status="draft",
        )

        response = self.client.get(self.list_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Active Flight")

    def test_unauthenticated_create_is_denied(self):
        response = self.client.post(self.list_url, data=self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unapproved_vendor_create_is_denied(self):
        self.client.force_authenticate(self.unapproved_vendor_user)

        response = self.client.post(self.list_url, data=self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approved_vendor_create_sets_owner_to_authenticated_vendor(self):
        self.client.force_authenticate(self.vendor_user)

        response = self.client.post(self.list_url, data=self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(id=response.data["id"])
        self.assertEqual(created.user_id, self.vendor_user.id)

    def test_admin_create_without_user_falls_back_to_admin(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(self.list_url, data=self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(id=response.data["id"])
        self.assertEqual(created.user_id, self.admin.id)

    def test_admin_create_with_null_user_falls_back_to_admin(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            data=self._payload(user=None),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(id=response.data["id"])
        self.assertEqual(created.user_id, self.admin.id)

    def test_admin_create_with_explicit_user_assigns_owner(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            data=self._payload(user=str(self.vendor_user.id)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Service.objects.get(id=response.data["id"])
        self.assertEqual(created.user_id, self.vendor_user.id)
