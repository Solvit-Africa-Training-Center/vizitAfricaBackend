from django.db import models
import uuid

class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField('bookings.Booking', on_delete=models.CASCADE, related_name='ticket')
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, related_name='tickets')
    pdf_url = models.URLField(blank=True)
    qr_code_data = models.TextField()
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"Ticket for Booking {self.booking.id}"
