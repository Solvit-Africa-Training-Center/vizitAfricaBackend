# payments/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.conf import settings
import json
import logging
import stripe

from .stripe_processor import StripePaymentProcessor
from bookings.models import Booking
from bookings.services import FinancialService
from .models import Payment
from accounts.utils.send_email import send_email

logger = logging.getLogger(__name__)


class CreatePaymentIntentView(APIView):
    """Create a Stripe PaymentIntent for a booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get("booking_id")
        
        if not booking_id:
            return Response(
                {"error": "booking_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Booking must be in ACCEPTED state to process payment
        if booking.status != Booking.Status.ACCEPTED:
            return Response(
                {"error": f"Cannot process payment for booking in {booking.status} state"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client_secret, payment_intent_id, amount_cents = StripePaymentProcessor.create_payment_intent(
                amount=booking.total_amount,
                currency=booking.currency.lower(),
                customer_email=request.user.email,
                metadata={
                    "booking_id": str(booking.id),
                    "user_id": str(request.user.id),
                }
            )

            # Create Payment record
            payment = Payment.objects.create(
                booking=booking,
                user=request.user,
                amount=booking.total_amount,
                currency=booking.currency,
                payment_method="stripe",
                transaction_id=payment_intent_id,
                status="pending",
            )

            return Response({
                "client_secret": client_secret,
                "payment_intent_id": payment_intent_id,
                "amount": float(booking.total_amount),
                "currency": booking.currency,
                "payment_id": str(payment.id),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConfirmPaymentView(APIView):
    """Confirm a payment and update booking status."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")
        card_data = request.data.get("card")
        payment_method_id = request.data.get("payment_method_id")
        
        if not payment_intent_id:
            return Response(
                {"error": "payment_intent_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get the payment intent from Stripe to verify it exists
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            booking_id = intent.metadata.get("booking_id")
            
            if not booking_id:
                return Response(
                    {"error": "Invalid payment intent - no booking ID"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            booking = Booking.objects.get(id=booking_id, user=request.user)
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving payment intent: {str(e)}")
            return Response(
                {"error": "Payment intent not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Get or create payment record
            payment, created = Payment.objects.get_or_create(
                transaction_id=payment_intent_id,
                defaults={
                    "booking": booking,
                    "user": request.user,
                    "amount": booking.total_amount,
                    "currency": booking.currency,
                    "payment_method": "stripe",
                    "status": "pending",
                }
            )
            
            # Confirm payment with Stripe (passing card data if provided)
            payment_result = StripePaymentProcessor.confirm_payment(
                payment_intent_id, 
                card_data,
                payment_method_id
            )
            
            if payment_result["status"] == "succeeded":
                # Update payment record
                payment.status = "succeeded"
                payment.save()

                # Update booking status
                booking.status = Booking.Status.PAID
                booking.payment_status = "succeeded"
                booking.payment_completed_at = timezone.now()
                booking.save()

                # Process financial transactions (Commission & Payout)
                try:
                    FinancialService.process_commission(booking)
                    FinancialService.process_payout(booking)
                except Exception as e:
                    logger.error(f"Error processing financial transactions for booking {booking.id}: {str(e)}")

                # Send confirmation emails
                self._send_payment_emails(booking, payment, request.user)

                return Response({
                    "status": "success",
                    "booking_status": booking.status,
                    "payment_status": payment.status,
                    "message": "Payment successful and booking confirmed",
                }, status=status.HTTP_200_OK)
            
            elif payment_result["status"] == "processing":
                payment.status = "processing"
                payment.save()
                
                return Response({
                    "status": "processing",
                    "message": "Payment is being processed",
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                payment.status = "failed"
                payment.save()
                
                error_msg = payment_result.get("error", "Payment failed")
                return Response({
                    "status": "failed",
                    "error": error_msg,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _send_payment_emails(self, booking, payment, user):
        """Send payment confirmation emails to user and admin."""
        try:
            # Email to user/guest
            user_context = {
                "guest_name": booking.user.full_name,
                "booking_id": booking.id,
                "currency": booking.currency,
                "amount": float(booking.total_amount),
                "payment_reference": payment.transaction_id,
                "payment_date": payment.created_at or timezone.now(),
            }
            
            user_html = render_to_string("emails/payment_received.html", user_context)
            send_email(
                subject=f"Payment Received - Booking {booking.id}",
                message="",
                html_message=user_html,
                recipient_list=[booking.user.email],
            )
            
            # Email to admin
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True, is_superuser=True)
            
            admin_context = {
                "guest_name": booking.user.full_name,
                "guest_email": booking.user.email,
                "booking_id": booking.id,
                "currency": booking.currency,
                "amount": float(booking.total_amount),
                "payment_reference": payment.transaction_id,
                "payment_date": payment.created_at or timezone.now(),
            }
            
            admin_html = render_to_string("emails/admin_payment_received.html", admin_context)
            send_email(
                subject=f"Payment Received - Booking {booking.id} (Admin Notification)",
                message="",
                html_message=admin_html,
                recipient_list=[admin.email for admin in admin_users if admin.email],
            )
            
            logger.info(f"Payment confirmation emails sent for booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Error sending payment emails: {str(e)}")


class StripeWebhookView(APIView):
    """Handle Stripe webhook events."""
    permission_classes = []  # Webhook doesn't need authentication

    @method_decorator(csrf_exempt)
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        # Validate webhook signature
        if not StripePaymentProcessor.validate_webhook_signature(payload, sig_header):
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            success, message = StripePaymentProcessor.handle_webhook_event(event)
            
            # Handle payment_intent events
            if event.get("type") == "payment_intent.succeeded":
                intent = event.get("data", {}).get("object", {})
                payment_intent_id = intent.get("id")
                metadata = intent.get("metadata", {})
                booking_id = metadata.get("booking_id")

                if booking_id:
                    try:
                        booking = Booking.objects.get(id=booking_id)
                        payment = Payment.objects.get(transaction_id=payment_intent_id)
                        
                        payment.status = "succeeded"
                        payment.save()
                        
                        booking.status = Booking.Status.PAID
                        booking.payment_status = "succeeded"
                        booking.payment_completed_at = timezone.now()
                        booking.save()

                        # Process financial transactions (Commission & Payout)
                        try:
                            FinancialService.process_commission(booking)
                            FinancialService.process_payout(booking)
                        except Exception as e:
                            logger.error(f"Error processing financial transactions for booking {booking_id} via webhook: {str(e)}")
                        
                        logger.info(f"Booking {booking_id} payment confirmed via webhook")
                    except (Booking.DoesNotExist, Payment.DoesNotExist) as e:
                        logger.warning(f"Could not update booking/payment from webhook: {str(e)}")

            elif event.get("type") == "payment_intent.payment_failed":
                intent = event.get("data", {}).get("object", {})
                payment_intent_id = intent.get("id")
                
                try:
                    payment = Payment.objects.get(transaction_id=payment_intent_id)
                    payment.status = "failed"
                    payment.save()
                    
                    booking = payment.booking
                    booking.payment_status = "failed"
                    booking.save()
                    
                    logger.info(f"Booking {booking.id} payment failed via webhook")
                except Payment.DoesNotExist:
                    logger.warning(f"Could not update payment from webhook")

            elif event.get("type") == "charge.refunded":
                charge = event.get("data", {}).get("object", {})
                payment_intent_id = charge.get("payment_intent")
                refund_id = charge.get("refunds", {}).get("data", [{}])[0].get("id")
                
                try:
                    payment = Payment.objects.get(transaction_id=payment_intent_id)
                    payment.status = "refunded"
                    payment.refund_id = refund_id
                    payment.save()
                    
                    booking = payment.booking
                    booking.status = Booking.Status.CANCELLED
                    booking.payment_status = "refunded"
                    booking.save()

                    # Process financial transactions (Internal Refund)
                    try:
                        FinancialService.process_refund(booking)
                    except Exception as e:
                        logger.error(f"Error processing internal refund for booking {booking.id} via webhook: {str(e)}")
                    
                    logger.info(f"Booking {booking.id} refunded via webhook")
                except Payment.DoesNotExist:
                    logger.warning(f"Could not update payment for refund webhook")

            return Response({"status": "received"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefundPaymentView(APIView):
    """Process refund for a paid booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get("booking_id")
        reason = request.data.get("reason", "Customer requested refund")
        
        if not booking_id:
            return Response(
                {"error": "booking_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking = Booking.objects.get(id=booking_id)
            # Allow refunds by admin or booking owner
            if booking.user != request.user and not request.user.is_staff:
                return Response(
                    {"error": "You don't have permission to refund this booking"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.status not in [Booking.Status.PAID, Booking.Status.COMPLETED]:
            return Response(
                {"error": f"Cannot refund booking in {booking.status} status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get the payment record
            payment = Payment.objects.filter(
                booking=booking,
                status="succeeded"
            ).first()
            
            if not payment:
                return Response(
                    {"error": "No successful payment found for this booking"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Process refund with Stripe
            success, refund_id = StripePaymentProcessor.refund_payment(
                payment.transaction_id,
                reason=reason
            )

            if success:
                # Update payment record
                payment.status = "refunded"
                payment.refund_id = refund_id
                payment.save()

                # Update booking status
                booking.status = Booking.Status.CANCELLED
                booking.payment_status = "refunded"
                booking.save()

                # Process financial transactions (Internal Refund)
                try:
                    FinancialService.process_refund(booking)
                except Exception as e:
                    logger.error(f"Error processing internal refund for booking {booking.id}: {str(e)}")

                # Send refund emails
                self._send_refund_emails(booking, payment, reason)

                return Response({
                    "status": "success",
                    "booking_status": booking.status,
                    "payment_status": payment.status,
                    "refund_id": refund_id,
                    "message": "Refund processed successfully",
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": "failed",
                    "error": f"Refund failed: {refund_id}",
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _send_refund_emails(self, booking, payment, reason):
        """Send refund notification emails to user and admin."""
        try:
            # Email to user/guest
            user_context = {
                "guest_name": booking.user.full_name,
                "booking_id": booking.id,
                "currency": booking.currency,
                "amount": float(payment.amount),
                "reason": reason,
                "refund_id": payment.refund_id,
                "refund_date": timezone.now(),
            }
            
            user_html = render_to_string("emails/refund_processed.html", user_context)
            send_email(
                subject=f"Refund Processed - Booking {booking.id}",
                message="",
                html_message=user_html,
                recipient_list=[booking.user.email],
            )
            
            # Email to admin
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True, is_superuser=True)
            
            admin_context = {
                "guest_name": booking.user.full_name,
                "guest_email": booking.user.email,
                "booking_id": booking.id,
                "currency": booking.currency,
                "amount": float(payment.amount),
                "reason": reason,
                "refund_id": payment.refund_id,
                "refund_date": timezone.now(),
            }
            
            admin_html = render_to_string("emails/admin_refund_processed.html", admin_context)
            send_email(
                subject=f"Refund Processed - Booking {booking.id} (Admin Notification)",
                message="",
                html_message=admin_html,
                recipient_list=[admin.email for admin in admin_users if admin.email],
            )
            
            logger.info(f"Refund notification emails sent for booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Error sending refund emails: {str(e)}")
