# payments/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import cashin_payment, cashout_payment

class CashInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")
        phone = request.data.get("phone_number")

        if not amount or not phone:
            return Response({"error": "amount and phone_number required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError
        except ValueError:
             return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        result = cashin_payment(amount_float, phone)
        return Response(result, status=status.HTTP_200_OK)


class CashOutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        amount = request.data.get("amount")
        phone = request.data.get("phone_number")

        if not amount or not phone:
            return Response({"error": "amount and phone_number required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError
        except ValueError:
             return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        result = cashout_payment(amount_float, phone)
        return Response(result, status=status.HTTP_200_OK)
