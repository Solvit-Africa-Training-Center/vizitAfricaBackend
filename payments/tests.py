from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User
from bookings.models import Booking
from unittest.mock import patch
import uuid

class PaymentTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_payment@example.com",
            password="password123",
            full_name="Test Payment"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_intent_missing_booking_id(self):
        url = reverse('create-payment-intent')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "booking_id is required"})

    def test_create_intent_invalid_status(self):
        booking = Booking.objects.create(
            user=self.user,
            total_amount=100.00,
            status=Booking.Status.PENDING
        )
        url = reverse('create-payment-intent')
        response = self.client.post(url, {"booking_id": str(booking.id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_intent_id_alias(self):
        booking = Booking.objects.create(
            user=self.user,
            total_amount=100.00,
            status=Booking.Status.ACCEPTED
        )
        url = reverse('create-payment-intent')
        with patch('payments.views.StripePaymentProcessor.create_payment_intent') as mock_create:
            mock_create.return_value = ("secret", "pi_123", 10000)
            response = self.client.post(url, {"id": str(booking.id)}, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['payment_intent_id'], "pi_123")
