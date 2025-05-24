from django.urls import path
from .views import (
    PackageListAPIView, BusListAPIView,
    PackageBookingListCreateAPIView, PackageBookingDetailAPIView,
    BusBookingListCreateAPIView, BusBookingDetailAPIView,
    TravelerCreateAPIView, PackageBookingTravelersAPIView, BusBookingTravelersAPIView,
    TravelerDetailAPIView, UserBookingsByStatus,CancelBookingView,PackageCategoryListAPIView,PackageSubCategoryListAPIView,SingleBusListAPIView,SinglePackageListAPIView,
    PopularBusApi,PackageBookingUpdateAPIView,PackageDriverDetailListAPIView,FooterSectionListAPIView,AdvertisementListAPIView

)

urlpatterns = [
    # Vendor resource endpoints
    path('packages/<int:category>/', PackageListAPIView.as_view(), name='package-list'),
    path('buses/', BusListAPIView.as_view(), name='bus-list'),

    path('bus/details/<int:bus_id>/',SingleBusListAPIView.as_view(),name="bus detail"),
    path('package/details/<int:package_id>/',SinglePackageListAPIView.as_view(),name="bus_details"),
    
    # Package booking endpoints
    path('bookings/package/', PackageBookingListCreateAPIView.as_view(), name='package-booking-list-create'),
    path('bookings/package/<int:pk>/', PackageBookingDetailAPIView.as_view(), name='package-booking-detail'),
    path('bookings/package/<int:booking_id>/travelers/', PackageBookingTravelersAPIView.as_view(), name='package-booking-travelers'),
    path('bookings/package/<int:booking_id>/edit/', PackageBookingUpdateAPIView.as_view(), name='package-booking-update'),
    
    # Bus ing endpoints
    path('bookings/bus/', BusBookingListCreateAPIView.as_view(), name='bus-booking-list-create'),
    path('bookings/bus/<int:pk>/', BusBookingDetailAPIView.as_view(), name='bus-booking-detail'),
    path('bookings/bus/<int:booking_id>/travelers/', BusBookingTravelersAPIView.as_view(), name='bus-booking-travelers'),

    path('bookings/cancel/',CancelBookingView.as_view(),name="booking_cancel"),
    
    # Bookstatus endpoints
    path('bookings/status/<str:status_filter>/', UserBookingsByStatus.as_view(), name='bookings-by-status'),
    
    # Trav endpoints
    path('travelers/create/', TravelerCreateAPIView.as_view(), name='traveler-create'),
    path('travelers/<int:pk>/', TravelerDetailAPIView.as_view(), name='traveler-detail'),

    path('services/categories/', PackageCategoryListAPIView.as_view(), name='package-category-list'),
    path('services/subcategories/<int:category>/', PackageSubCategoryListAPIView.as_view(), name='package-subcategory-list'),

    path('popular-buses/',PopularBusApi.as_view(),name="Popular-buses"),

    path('package-drivers/<int:booking_id>/', PackageDriverDetailListAPIView.as_view(), name='package-drivers'),

    path('footer-sections/', FooterSectionListAPIView.as_view(), name='footer-section-list'),

    path('advertisements/', AdvertisementListAPIView.as_view(), name='advertisement-list'),
]