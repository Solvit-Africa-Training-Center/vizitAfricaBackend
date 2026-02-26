import stripe
from django.conf import settings
from decimal import Decimal
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePaymentProcessor:
    """Handles all Stripe payment operations and webhook processing."""

    @staticmethod
    def create_payment_intent(
        amount: Decimal,
        currency: str = "usd",
        customer_email: str = "",
        metadata: Optional[Dict] = None,
    ) -> Tuple[str, str, int]:
        """
        Create a Stripe PaymentIntent for a booking.
        
        Args:
            amount: Amount in the smallest currency unit (cents for USD)
            currency: Currency code (default: usd)
            customer_email: Customer email for payment
            metadata: Additional metadata to attach to intent
            
        Returns:
            Tuple of (client_secret, payment_intent_id, amount_in_cents)
        """
        try:
            # Convert amount to cents if needed
            amount_cents = int(amount * 100) if isinstance(amount, Decimal) else int(amount)

            intent_metadata = metadata or {}
            intent_metadata.update({"currency": currency})

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                payment_method_types=["card"],
                receipt_email=customer_email,
                metadata=intent_metadata,
            )

            logger.info(
                f"Created PaymentIntent: {intent.id} for amount {amount_cents} {currency}"
            )

            return intent.client_secret, intent.id, amount_cents
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating PaymentIntent: {str(e)}")
            raise Exception(f"Payment processing error: {str(e)}")

    @staticmethod
    def confirm_payment(payment_intent_id: str, card_data: Optional[Dict] = None, payment_method_id: Optional[str] = None) -> Dict:
        """
        Confirm a payment intent. If card_data or payment_method_id is provided, 
        it will be used to confirm the payment.
        
        Args:
            payment_intent_id: Stripe PaymentIntent ID
            card_data: Optional card details dict with keys: number, exp_month, exp_year, cvc, name
            payment_method_id: Optional pre-created payment method ID (e.g., from tok_visa)
                      
        Returns:
            Dict with payment status details
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # If card data or payment method ID provided, confirm payment
            if card_data or payment_method_id:
                try:
                    pm_id = payment_method_id
                    
                    # If payment_method_id starts with 'tok_', it's actually a token, 
                    # we need to create a PaymentMethod from it first.
                    if pm_id and pm_id.startswith('tok_'):
                        payment_method = stripe.PaymentMethod.create(
                            type="card",
                            card={"token": pm_id},
                        )
                        pm_id = payment_method.id
                    
                    # If card data provided and no payment_method_id, create payment method
                    elif card_data and not pm_id:
                        # Create a payment method from card details
                        payment_method = stripe.PaymentMethod.create(
                            type="card",
                            card={
                                "number": card_data.get("number"),
                                "exp_month": int(card_data.get("exp_month")),
                                "exp_year": int(card_data.get("exp_year")),
                                "cvc": card_data.get("cvc"),
                            },
                            billing_details={
                                "name": card_data.get("name"),
                            }
                        )
                        pm_id = payment_method.id
                    
                    # Confirm the payment intent with the payment method
                    intent = stripe.PaymentIntent.confirm(
                        payment_intent_id,
                        payment_method=pm_id,
                    )
                    
                    logger.info(f"Confirmed PaymentIntent {payment_intent_id}")
                    
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe error creating/confirming with card: {str(e)}")
                    return {
                        "status": "failed",
                        "error": str(e),
                        "payment_intent_id": payment_intent_id,
                    }
            
            # Map intent status to our status format
            status_map = {
                "succeeded": "succeeded",
                "processing": "processing",
                "requires_payment_method": "failed",
                "requires_action": "requires_action",
                "canceled": "failed",
            }

            return {
                "status": status_map.get(intent.status, "failed"),
                "amount": intent.amount / 100,  # Convert back to dollars
                "currency": intent.currency.upper(),
                "payment_intent_id": intent.id,
                "error": intent.last_payment_error.message if intent.last_payment_error else None,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "payment_intent_id": payment_intent_id,
            }

    @staticmethod
    def handle_webhook_event(event_data: Dict) -> Tuple[bool, str]:
        """
        Process Stripe webhook events.
        
        Args:
            event_data: Raw webhook event data from Stripe
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        event_type = event_data.get("type")
        intent = event_data.get("data", {}).get("object", {})

        try:
            if event_type == "payment_intent.succeeded":
                return True, f"Payment succeeded: {intent.get('id')}"
            
            elif event_type == "payment_intent.payment_failed":
                return False, f"Payment failed: {intent.get('id')}"
            
            elif event_type == "payment_intent.canceled":
                return False, f"Payment canceled: {intent.get('id')}"
            
            elif event_type == "charge.refunded":
                return True, f"Charge refunded: {intent.get('id')}"
            
            else:
                return True, f"Unhandled event type: {event_type}"

        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            return False, str(e)

    @staticmethod
    def refund_payment(payment_intent_id: str, reason: str = "") -> Tuple[bool, str]:
        """
        Refund a successful payment.
        
        Args:
            payment_intent_id: Stripe PaymentIntent ID to refund
            reason: Reason for refund
            
        Returns:
            Tuple of (success: bool, refund_id: str)
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status != "succeeded":
                return False, "Payment not yet succeeded"

            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                reason=reason or "requested_by_customer",
            )

            logger.info(f"Created refund: {refund.id} for payment intent {payment_intent_id}")
            return True, refund.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error refunding payment: {str(e)}")
            return False, str(e)

    @staticmethod
    def validate_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        Validate that a webhook came from Stripe.
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header value
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET,
            )
            return True
        except ValueError:
            logger.warning("Invalid webhook payload")
            return False
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid webhook signature")
            return False
