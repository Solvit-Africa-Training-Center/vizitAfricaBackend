from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateBookingItemView, UpdateBookingItemView, BookingItemListView,
    ConfirmBookingView, BookingListView, BookingDetailView, TripSubmissionView, 
    generate_ticket, download_ticket, verify_ticket, process_commission, 
    transaction_history, process_refund, vendor_payouts, process_payout, 
    AdminBookingListView, AdminBookingDetailView, PackageViewSet, PackageItemViewSet,
    send_quote, accept_quote, cancel_booking, notify_vendor
)

router = DefaultRouter()
router.register(r'admin/packages', PackageViewSet, basename='admin-package')
router.register(r'admin/package-items', PackageItemViewSet, basename='admin-package-item')

urlpatterns = [
    # Booking Items (Cart)
    path('items/', BookingItemListView.as_view(), name='booking-items-list'),
    path('items/create/', CreateBookingItemView.as_view(), name='create-booking-item'),
    path('items/<uuid:pk>/update/', UpdateBookingItemView.as_view(), name='update-booking-item'),
    path('items/<uuid:pk>/', UpdateBookingItemView.as_view(), name='delete-booking-item'),
    
    # Bookings
    path('submit-trip/', TripSubmissionView.as_view(), name='submit-trip'),
    path('confirm/', ConfirmBookingView.as_view(), name='confirm-booking'),
    path('', BookingListView.as_view(), name='bookings-list'),
    path('<uuid:pk>/', BookingDetailView.as_view(), name='booking-detail'),

    # Ticket Generation
    path('<uuid:booking_id>/generate-ticket/', generate_ticket, name='generate-ticket'),
    path('<uuid:booking_id>/download-ticket/', download_ticket, name='download-ticket'),
    path('verify-ticket/', verify_ticket, name='verify-ticket'),

    # Transactions
    path('<uuid:booking_id>/commission/', process_commission, name='process-commission'),
    path('<uuid:booking_id>/payout/', process_payout, name='process-payout'),
    path('<uuid:booking_id>/refund/', process_refund, name='process-refund'),
    path('transactions/', transaction_history, name='transaction-history'),
    path('vendor-payouts/', vendor_payouts, name='vendor-payouts'),
    
    # Admin
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin-bookings-list'),
    path('admin/bookings/<uuid:pk>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),
    
    # RESTful Quote Management
    path('<uuid:booking_id>/quote/', send_quote, name='manage-quote'),
    path('<uuid:booking_id>/accept/', accept_quote, name='accept-quote'),
    path('<uuid:booking_id>/cancel/', cancel_booking, name='cancel-booking'),
    path('<uuid:booking_id>/notify-vendor/', notify_vendor, name='notify-vendor'),

    path('', include(router.urls)),
]
