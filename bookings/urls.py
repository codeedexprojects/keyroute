from django.urls import path
from .views import (
    PackageListAPIView, BusListAPIView,
    PackageBookingListCreateAPIView, PackageBookingDetailAPIView,
    BusBookingListCreateAPIView, BusBookingDetailAPIView,
    TravelerCreateAPIView, PackageBookingTravelersAPIView, BusBookingTravelersAPIView,
    TravelerDetailAPIView, BookingsByStatusAPIView,CancelBookingView
)

urlpatterns = [
    # Vendor resource endpoints
    path('packages/', PackageListAPIView.as_view(), name='package-list'),
    path('buses/', BusListAPIView.as_view(), name='bus-list'),
    
    # Package booking endpoints
    path('bookings/package/', PackageBookingListCreateAPIView.as_view(), name='package-booking-list-create'),
    path('bookings/package/<int:pk>/', PackageBookingDetailAPIView.as_view(), name='package-booking-detail'),
    path('bookings/package/<int:booking_id>/travelers/', PackageBookingTravelersAPIView.as_view(), name='package-booking-travelers'),
    
    # Bus ing endpoints
    path('bookings/bus/', BusBookingListCreateAPIView.as_view(), name='bus-booking-list-create'),
    path('bookings/bus/<int:pk>/', BusBookingDetailAPIView.as_view(), name='bus-booking-detail'),
    path('bookings/bus/<int:booking_id>/travelers/', BusBookingTravelersAPIView.as_view(), name='bus-booking-travelers'),

    path('bookings/<str:booking_type>/cancel/',CancelBookingView.as_view(),name="booking_cancel"),
    
    # Bookstatus endpoints
    path('bookings/<str:booking_type>/status/<str:status>/', BookingsByStatusAPIView.as_view(), name='bookings-by-status'),
    
    # Trav endpoints
    path('travelers/create/', TravelerCreateAPIView.as_view(), name='traveler-create'),
    path('travelers/<int:pk>/', TravelerDetailAPIView.as_view(), name='traveler-detail'),
]