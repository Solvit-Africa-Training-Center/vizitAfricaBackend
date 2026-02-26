from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

class AccountTests(APITestCase):
    def test_set_password_endpoint(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="old_password",
            full_name="Test User",
            phone_number="1234567890"
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # Test the new URL pattern
        url = f"/api/accounts/users/set_password/{uidb64}/{token}/"
        data = {
            "password": "new_password123",
            "re_password": "new_password123"
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        
        # Verify password was changed
        user.refresh_from_db()
        self.assertTrue(user.check_password("new_password123"))
