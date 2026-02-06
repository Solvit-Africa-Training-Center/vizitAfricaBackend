# payments/services.py
from .paypack_client import transaction

def cashin_payment(amount: float, phone_number: str):
    """Perform cashin transaction"""
    try:
        response = transaction.cashin(amount=amount, phone_number=phone_number)
        return response
    except Exception as e:
        return {"error": str(e)}

def cashout_payment(amount: float, phone_number: str):
    """Perform cashout transaction"""
    try:
        response = transaction.cashout(amount=amount, phone_number=phone_number)
        return response
    except Exception as e:
        return {"error": str(e)}
