from django.urls import path
from .views import *
from bookings.views import VendorBusBookingAPI,VendorPackageBookingAPI,VendorBusBookingByStatusAPI,VendorPackageBookingByStatusAPI

urlpatterns = [
   path('api/vendor/signup/', VendorSignupAPIView.as_view(), name='vendor-signup'),
   path('api/vendor/login/', LoginAPIView.as_view(), name='vendor_login'),
   path('api/vendor/logout/', LogoutAPIView.as_view(), name='logout'),

    path('api/vendor/send-otp/', SendOtpAPIView.as_view(), name='send_otp'),
    path('api/vendor/verify-otp/', VerifyOtpAPIView.as_view(), name='verify_otp'),
    path('api/vendor/reset-password/', ResetPasswordAPIView.as_view(), name='reset_password'),


    # BUS FEATURE
    path('api/busfeatures/create/', BusFeatureCreateAPIView.as_view(), name='busfeature-create'),
    
    # BUS REGISTRATION
    path('api/vendor/amenities/', AmenityCreateAPIView.as_view(), name='create-amenity'),
    path('api/vendor/bus/', BusAPIView.as_view(), name='bus_details'),
    path('api/vendor/bus/<int:bus_id>/', BusEditAPIView.as_view(), name='bus_edit'),


    # PACKAGE CATEGORY
    path('api/vendor/package-category/', PackageCategoryAPIView.as_view(), name='bus_details'),
    path('api/vendor/package-category/<int:pk>/', PackageCategoryAPIView.as_view(), name='package-category-update-delete'),

    # SUBCATEGORY
    path('api/vendor/package-subcategory/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-list-create'),
    path('api/vendor/package-subcategory/<int:pk>/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-detail'),

    # PACKAGE 
    path('api/vendor/package/', PackageAPIView.as_view(), name='package-create-list'),
    path('api/vendor/package/<int:package_id>/', PackageAPIView.as_view(), name='package-detail'), 

    # PROFILE
    path('api/vendor/profile/', VendorProfileAPIView.as_view(), name='vendor-profile'),

    # CHANGE PASSWORD
    path('api/vendor/change-password/', ChangePasswordAPIView.as_view(), name='vendor-profile'),

    # BANK DETAILS
    path('api/vendor/bank-details/', VendorBankDetailView.as_view(), name='vendor-bank-details'),


    #Booking
    path('api/vendor/bus/bookings/',VendorBusBookingAPI.as_view(),name="vendor-bus-booking-list"),
    path('api/vendor/package/bookings/',VendorPackageBookingAPI.as_view(),name="vendor-package-booking-list"),
    path('api/vendor/bus/bookings/<str:booking_status>/',VendorBusBookingByStatusAPI.as_view(),name="vendor-bus-booking-status"),
    path('api/vendor/package/bookings/<str:booking_status>/',VendorPackageBookingByStatusAPI.as_view(),name="vendor-package-booking-status"),
]
