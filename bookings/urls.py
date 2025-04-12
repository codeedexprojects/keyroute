from django.urls import path
from .views import (
    BookingListCreateAPIView, BookingDetailAPIView,
    AddTravelerAPIView, TravelerListAPIView, TravelerDetailAPIView,
    MakePaymentAPIView, PaymentListAPIView,
    CancellationPolicyListAPIView, CancellationPolicyDetailAPIView
)

urlpatterns = [
    # Booking endpoints
    path('api/user/bookings/', BookingListCreateAPIView.as_view(), name='booking-list-create'),
    path('api/user/bookings/<int:pk>/', BookingDetailAPIView.as_view(), name='booking-detail'),
    
    # Traveler endpoints
    path('api/user/bookings/<int:booking_id>/travelers/', TravelerListAPIView.as_view(), name='traveler-list'),
    path('api/user/bookings/<int:booking_id>/travelers/add/', AddTravelerAPIView.as_view(), name='add-traveler'),
    path('api/user/travelers/<int:pk>/', TravelerDetailAPIView.as_view(), name='traveler-detail'),
    
    # Payment endpoints
    path('api/user/bookings/<int:booking_id>/payments/make/', MakePaymentAPIView.as_view(), name='make-payment'),
    path('api/user/bookings/<int:booking_id>/payments/', PaymentListAPIView.as_view(), name='payment-list'),
    
    # Cancellation policy endpoints
    path('api/user/cancellation-policies/', CancellationPolicyListAPIView.as_view(), name='cancellation-policy-list'),
    path('api/user/packages/<int:package_id>/cancellation-policy/', CancellationPolicyDetailAPIView.as_view(), name='cancellation-policy-detail'),
]