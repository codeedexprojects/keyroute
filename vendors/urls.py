from django.urls import path
from .views import *
from bookings.views import CompleteTripAPIView,VendorPackageBookingAPI,VendorBusBookingByStatusAPI,VendorPackageBookingByStatusAPI,BookingFilterByDate
from reviews.views import VendorAllReviewsView
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
    path('api/vendor/package-subcategory/<int:pk>/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-list-create'),
    # path('api/vendor/package-subcategory/<int:pk>/', PackageSubCategoryAPIView.as_view(), name='package-subcategory-detail'),

    # PACKAGE 
    path('api/vendor/package/', PackageAPIView.as_view(), name='package-create-list'),
    # DAYS DELETING
    path('api/vendor/day-plan/delete/<int:day_id>/', DayPlanDeleteAPIView.as_view(), name='delete_day_plan'),


    # single package LISTING
    path('api/vendor/package/<int:package_id>/', PackageAPIView.as_view(), name='package-detail'), 

    # NEW PACKAGE CREATING OLD
    path('api/vendor/packages/create/', BasicPackageAPIView.as_view(), name='create-package'),
    # PACKAGE EDIT
    path('api/vendor/packages/<int:package_id>/edit/', PackageEditAPIView.as_view(), name='edit-package'),
    # ADD DAYS
    # path('api/vendor/packages/<int:package_id>/add-day-plans/', DayPlanCreateAPIView.as_view(), name='add-day-plans'),


    # LATEST PACKAGE CREATING SINGLE ONE DAYS -------------------------
    path('api/vendor/packages-days/create', CreatePackageAndDayPlanAPIView.as_view(), name='create-package'),
    path('api/vendor/dayplans/<day_id>/edit/', EditDayPlanAPIView.as_view(), name='edit-days'),
    # ADD DAYS SEPREATE
    path('api/vendor/packages/<package_id>/add-day/', AddDayPlanAPIView.as_view(), name='add-days'),
    path('api/vendor/packages/<package_id>/single-day/<day_number>', AddDayPlanAPIView.as_view(), name='single-days'),





    # PROFILE
    path('api/vendor/profile/', VendorProfileAPIView.as_view(), name='vendor-profile'),

    # CHANGE PASSWORD
    path('api/vendor/change-password/', ChangePasswordAPIView.as_view(), name='vendor-profile'),

    # BANK DETAILS
    path('api/vendor/bank-details/', VendorBankDetailView.as_view(), name='vendor-bank-details'),


    #Booking
    # path('api/vendor/bus/bookings/',VendorBusBookingAPI.as_view(),name="vendor-bus-booking-list"),
    # path('api/vendor/package/bookings/',VendorPackageBookingAPI.as_view(),name="vendor-package-booking-list"),
    # path('api/vendor/bus/bookings/<str:booking_status>/',VendorBusBookingByStatusAPI.as_view(),name="vendor-bus-booking-status"),
    # path('api/vendor/package/bookings/<str:booking_status>/',VendorPackageBookingByStatusAPI.as_view(),name="vendor-package-booking-status"),


    # NOTIFICATION
    path('api/vendor/notifications/', VendorNotificationListView.as_view(), name='vendor-notifications'),
    path('api/vendor/notifications/<int:notification_id>/read/', MarkNotificationAsReadView.as_view(), name='mark-notification-read'),


    # REVENUE
    path('api/vendor/revenue/', VendorTotalRevenueView.as_view(), name='vendor-total-revenue'),
    path('api/vendor/bus-revenue/', BusBookingRevenueListView.as_view(), name='vendor-bus-revenue'),
    path('api/vendor/package-revenue/', PackageBookingRevenueListView.as_view(), name='vendor-package-revenue'),

    # LATEST BOOKING 
    path('api/vendor/latest/', LatestSingleBookingView.as_view(), name='latest-bus-bookings'),
    
    # LATEST BOOKING DETAILS VIEW
    path('api/booking-detail/<int:booking_id1>/', BookingDetailByIdView.as_view()),

    # Latest BOOKING VIEW
    path('api/vendor/booking/detail/<int:booking_id>/', UnifiedBookingDetailView.as_view(), name='unified_booking_detail'),
 
    # LASTEST BOOKING COMPLETED HISTORY SINGLE
    path('api/vendor/latest/booking-history/', VendorLatestSingleBookingHistoryView.as_view(), name='latest-bookings-history'),

    # LATEST CANCEL
    path('api/vendor/latest-canceled-booking/', LatestCanceledBookingView.as_view(), name='latest-canceled-booking'),
   
#    BOOKING HISTORY BUS
    path('api/vendor/bus-booking/', VendorBusBookingListView.as_view(), name='bus-booking-list'),
    path('api/vendor/package-booking/', PackageBookingListView.as_view(), name='bus-booking-list'),
   

    # SIGNLE BOOKING HISTORY BUS AND PACKAGE
    path('api/vendor/bus-booking/<int:booking_id>/', BusBookingDetailView.as_view(), name='bus-booking-detail'),
    path('api/vendor/package-booking-history/<int:booking_id>/', SinglePackageBookingDetailView.as_view(), name='single-package-booking-detail'),
    





    #BOOKING HISTORIES FILTER BUS AND PACKAGE SIDE
    path('api/vendor/package-history-filter/', PackageBookingHistoryFilterView.as_view(), name='package-history-filter'),
    path('api/vendor/bus-history-filter/', BusHistoryFilterView.as_view(), name='bus-history-filter'),




    # CANCELD BUS
    path('api/vendor/canceled-bus-bookings/', CanceledBusBookingView.as_view(), name='canceled-bus-booking-list'),
    path('api/vendor/canceled-bus-bookings-filter/', CanceledBusBookingFilterView.as_view(), name='BUS-CANCELD-filter'),
    path('api/vendor/canceled-bus-bookings-single/<int:booking_id>/', CanceledBusBookingFilterView.as_view(), name='BUS-CANCELD-single'),

    # CANCELD PACKAGE and FILTER
    path('api/vendor/canceled-package-bookings/', CanceledPackageBookingView.as_view(), name='canceled-package-booking-list'),
    path('api/vendor/canceled-package-bookings/<int:booking_id>/', CanceledPackageBookingView.as_view(), name='canceled-package-booking-detail'),
    path('api/vendor/canceled-package-bookings-filter/', CanceledPackageBookingFilterView.as_view(), name='PACKAGE-CANCELD-filter'),

    # path('api/package-booking/latest/', LatestPackageBookingDetailView.as_view(), name='latest-package-booking-detail'),


    # EARNINGS BUS + PACKAGE
    path('api/vendor/bus-booking-earnings/', BusBookingEarningsHistoryView.as_view(), name='vendor-bus-revenue'),   
    path('api/vendor/package-booking-earnings/', PackageBookingEarningsView.as_view(), name='package-booking-basic-history'),

    path('api/vendor/packages/<int:pk>/edit/', PackageUpdateAPIView.as_view(), name='package-update'),
    # # SINGLE BUS BOOKING HISTORY
    # path('api/vendor/bus-booking-history/<int:booking_id>/', SingleBusBookingDetailView.as_view(), name='single-bus-booking-detail'),
    
   
    
    
    # FILTER EARNINGS BUS AND PACKAGE
    path('api/vendor/bus-earnings-history-filter/', BusBookingEarningsHistoryFilterView.as_view(), name='bus-history-filter'),
    path('api/vendor/package-earnings-history-filter/', PackageBookingEarningsFilterView.as_view(), name='bus-history-filter'),



    # MARK EVENT
    path('api/vendor/busy-date/', VendorBusyDateCreateView.as_view(), name='create-busy-date'),
    path('api/vendor/busy-date/<int:pk>/', VendorBusyDateCreateView.as_view(), name='create-busy-date'),

    path('api/vendor/booking/<str:booking_type>/filter/<str:date>/', BookingFilterByDate.as_view(), name='booking-by-filter'),

    # BOOKING ACCEPTED AND DECLINED BUS
    path('api/vendor/accepted-bus-bookings/', AcceptedBusBookingListView.as_view(), name='accepted-bus-bookings'),
    path('api/vendor/declined-bus-bookings/', DeclinedBusBookingListView.as_view(), name='declined-bus-bookings'),


    # ACCEPTED SINGLE DATAS BUS AND PACKAGE
    path('api/vendor/accepted-bus-booking-detail/<int:booking_id1>/', AcceptedBusBookingDetailView.as_view(),name='accepted_bus_booking_detail'),
    path('api/vendor/accepted-package-booking/<int:booking_id1>/', AcceptedPackageBookingDetailView.as_view(), name='accepted_package_booking_detail'),


    #PACKAGE ACCEPTED DECLIED LIST
    path('api/vendor/accepted-package-bookings/', AcceptedPackageBookingListView.as_view(), name='accepted_package_booking_list'),
    path('api/vendor/decline-package-booking/', DeclinePackageBookingView.as_view(), name='decline_package_booking'),

    # REQUEST ACCEPT
    path('api/vendor/accepting-bus-bookings/<int:booking_id1>/', AcceptBusBookingView.as_view(), name='accept-bus-bookings'),
    path('api/vendor/accepting-package-bookings/<int:booking_id1>/', AcceptPackageBookingView.as_view(), name='accept-package-bookings'),
    
    
    
    # DECLAINED BUS AND PACKAGE
    path('api/vendor/declined-bus-bookings/<int:booking_id1>/', DeclineBusBookingView.as_view(), name='Decline-bus-bookings'),
    path('api/vendor/declined-package-bookings/<int:booking_id1>/', DeclinePackageBookingView.as_view(), name='Decline-pckage-bookings'),



    # REQUEST LIST
    path('api/vendor/request-list-bus-bookings/', BusBookingRequestListView.as_view(), name='reqst-list-bus-bookings'),
    path('api/vendor/request-list-package-bookings/', PackageBookingRequestView.as_view(), name='reqst-list-package-bookings'),

    # PRE ACCEPTING BOOKING VIEW
    path('api/vendor/prerequest-view/<int:booking_id1>/', PreAcceptPackageBookingDetailView.as_view(), name='pre-requst'),



    

    # REVIEWS
    path('api/vendor/reviews/', VendorAllReviewsView.as_view(), name='vendor_all_reviews'),


    

    # 

    # TRANSATION HISTORY
    path('api/vendor/transaction-history/', VendorTransactionHistoryAPIView.as_view(), name='vendor-transaction-history'),
   

    path('api/vendor/booking/complete/', CompleteTripAPIView.as_view(), name='complete_trip'),


    path('api/vendor/delete-account/', DeleteVendorAccountView.as_view(), name='delete-vendor-account'),
    path('api/vendor/verify-rc/', VehicleRCVerificationView.as_view(), name='verify-rc'),


]
