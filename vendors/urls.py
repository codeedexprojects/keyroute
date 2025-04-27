from django.urls import path
from .views import *
from bookings.views import VendorBusBookingAPI,VendorPackageBookingAPI,VendorBusBookingByStatusAPI,VendorPackageBookingByStatusAPI,BookingFilterByDate

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
    # path('api/vendor/package-category/<int:pk>/', PackageCategoryAPIView.as_view(), name='package-category-update-delete'),

    # SUBCATEGORY LISTING
    path('api/vendor/package-subcategory/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-list-create'),
    # path('api/vendor/package-subcategory/<int:pk>/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-detail'),

    # PACKAGE 
    path('api/vendor/package/', PackageAPIView.as_view(), name='package-create-list'),
    path('api/vendor/package/<int:package_id>/', PackageAPIView.as_view(), name='package-detail'), 

    # NEW
    path('packages/create/', BasicPackageAPIView.as_view(), name='create-package'),
    path('packages/<int:package_id>/add-day-plans/', DayPlanCreateAPIView.as_view(), name='add-day-plans'),











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


    # NOTIFICATION
    path('api/vendor/notifications/', VendorNotificationListView.as_view(), name='vendor-notifications'),
    path('api/vendor/notifications/<int:notification_id>/read/', MarkNotificationAsReadView.as_view(), name='mark-notification-read'),


    # REVENUE
    path('api/vendor/revenue/', VendorTotalRevenueView.as_view(), name='vendor-total-revenue'),
    path('api/vendor/bus-revenue/', BusBookingRevenueListView.as_view(), name='vendor-bus-revenue'),
    path('api/vendor/package-revenue/', PackageBookingRevenueListView.as_view(), name='vendor-package-revenue'),

    # LATEST BOOKING 
    path('api/vendor/latest/', LatestSingleBookingView.as_view(), name='latest-bus-bookings'),

    # LATEST CANCEL
    path('api/vendor/latest-canceled-booking/', LatestCanceledBookingView.as_view(), name='latest-canceled-booking'),
   
   
   
    path('api/bus-booking/<int:booking_id>/', BusBookingDetailView.as_view(), name='bus-booking-detail'),
    path('api/package-booking/latest/', LatestPackageBookingDetailView.as_view(), name='latest-package-booking-detail'),


    # BOOKING HISTORY FROM BUS SIDE
    path('api/vendor/busbasichistory/', BusBookingBasicHistoryView.as_view(), name='vendor-bus-revenue'),
    path('api/vendor/bus-booking-history/<int:booking_id>/', SingleBusBookingDetailView.as_view(), name='single-bus-booking-detail'),
    # FILTER
    path('api/vendor/bus-history-filter/', BusBookingHistoryFilterView.as_view(), name='bus-history-filter'),


    # BOOKING HISTORY FROM PACKAGE SIDE
    path('api/package-booking-history/', PackageBookingBasicHistoryView.as_view(), name='package-booking-basic-history'),
    path('api/package-booking-history/<int:booking_id>/', SinglePackageBookingDetailView.as_view(), name='single-package-booking-detail'),
    

    # MARK EVENT
    path('api/vendor/busy-date/', VendorBusyDateCreateView.as_view(), name='create-busy-date'),
    path('api/vendor/busy-date/<int:pk>/', VendorBusyDateCreateView.as_view(), name='create-busy-date'),

    path('api/vendor/booking/<str:booking_type>/filter/<str:date>/', BookingFilterByDate.as_view(), name='booking-by-filter'),
]
