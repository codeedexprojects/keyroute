from django.urls import path
from .views import (
    BookingListCreateAPIView, BookingDetailAPIView,
    AddTravelerAPIView, TravelerListAPIView, TravelerDetailAPIView,
    ListPackage,BookingDetailsByStatus
)

urlpatterns = [
    # Package endpoints
    path('api/users/packages/', ListPackage.as_view(), name='package-list'),
    
    # Booking endpoints
    path('api/users/bookings/', BookingListCreateAPIView.as_view(), name='booking-list-create'),
    path('api/users/bookings/<int:pk>/', BookingDetailAPIView.as_view(), name='booking-detail'),
    path('api/users/bookings/status/<str:status>/', BookingDetailsByStatus.as_view()),
    
    # Traveler endpoints
    path('api/users/bookings/<int:booking_id>/travelers/', TravelerListAPIView.as_view(), name='traveler-list'),
    path('api/users/bookings/<int:booking_id>/travelers/add/', AddTravelerAPIView.as_view(), name='add-traveler'),
    path('api/users/travelers/<int:pk>/', TravelerDetailAPIView.as_view(), name='traveler-detail')
]