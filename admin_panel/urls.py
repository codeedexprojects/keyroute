from django.urls import path
from admin_panel.views import *
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

urlpatterns = [
    path('api/admin/login/', AdminLoginAPIView.as_view(), name='admin-login'),
    
    # VENDOR
    # path('api/admin/vendors/list', VendorListAPIView.as_view(), name='vendor-list'),
    # path('api/admin/vendor/<int:vendor_id>/', VendorDetailAPIView.as_view(), name='vendor-detail'),

    # COUNT
    path('api/admin/vendor/count/', VendorCountAPIView.as_view(), name='vendor-count'),
    path('api/admin/user/count/', UserCountAPIView.as_view(), name='user-count'),

    # RECENT USERS
    path('api/admin/recent-user/', RecentlyJoinedUsersAPIView.as_view(), name='recent-users'),

    # BUSLIST
    path('api/admin/tottel-buses/', AdminBusListAPIView.as_view(), name='admin-bus-list'),


    # USERS LIST
    path('api/admin/users/', AllUsersAPIView.as_view(), name='all-users'),
    path('api/admin/users/<int:user_id>/', AllUsersAPIView.as_view(), name='single-user'),
    #USER PDF
    path('api/admin/users/pdf/', AllUsersPDFAPIView.as_view(), name='users-pdf'),

    # VENODR CREATING AND LISING
    path('api/admin/create-vendor/', AdminCreateVendorAPIView.as_view(), name='admin-create-vendor'),
    path('api/admin/vendors/list/', AdminCreateVendorAPIView.as_view(), name='admin-create-vendor'),

    # VENDOR SINGLE DATA
    path('api/admin/vendors/<int:vendor_id>/', AdminVendorDetailAPIView.as_view(), name='admin-vendor-detail'),

    # SINGLE VENDOR BUS LIST
    path('api/admin/vendors/<int:vendor_id>/buses/', AdminVendorBusListAPIView.as_view()),

    

    # PACKAGE LISTING by vendor id  AND SINGLE DETAILS
    path('api/admin/vendor/<int:vendor_id>/packages/', AdminVendorPackageListAPIView.as_view()),
    path('api/admin/vendor/package/<int:package_id>/', AdminPackageDetailAPIView.as_view()),


    # CATEGORY
    path('api/admin/categories/', PackageCategoryListAPIView.as_view()),

    # NORMAL USER CREATING
    path('api/admin/create-user/', AdminCreateUserView.as_view(), name='admin-create-user'),

    #Advertisement CREATING AND LISTING
    # path('api/admin/sections/', AllSectionsCreateView.as_view(), name='create-sections'),
    # path('api/admin/advertisement/<int:ad_id>/', AdvertisementDetailView.as_view(), name='advertisement-detail'),

    # ADV , LIMITED DEAL,FOOTER, REFER LISTING ----------------------------------------
    path('api/admin/advertisement/<int:ad_id>/', AdvertisementDetailView.as_view()),
    path('api/admin/limited-deals/', LimitedDealListView.as_view()),
    path('api/admin/limited-deals/<int:deal_id>/', LimitedDealDetailView.as_view()),
    path('api/admin/footer-sections/', FooterSectionListView.as_view()),
    path('api/admin/footer-sections/<int:footer_id>/', FooterSectionDetailView.as_view()),
    path('api/admin/refer-and-earn/', ReferAndEarnListView.as_view()),
    path('api/admin/refer-and-earn/<int:ref_id>/', ReferAndEarnDetailView.as_view()),

# -----------------------------------------------------------

    # CREATING

    path('api/admin/create/advertisement/', AdvertisementCreateView.as_view(), name='create_advertisement'),
    path('api/admin/create/limited-deal/', LimitedDealCreateView.as_view(), name='create_limited_deal'),
    path('api/admin/create/footer-section/', FooterSectionCreateView.as_view(), name='create_footer_section'),
    path('api/admin/create/refer-and-earn/', ReferAndEarnCreateView.as_view(), name='create_refer_and_earn'),

# -----------------------------

    # EXPLORE
    path('api/admin/explore/create/', ExploreSectionCreateView.as_view(), name='create-explore-section'),
    # edit
    path('api/admin/explore/<int:pk>/', ExploreSectionCreateView.as_view(), name='create-explore-section'),

    # EXPLORE LISTING
    path('api/admin/explore/list/', ExploreSectionListView.as_view(), name='explore-list'),


    #ALL BOOKINGS
    path('api/admin/all-bookings/', AdminBookingListView.as_view(), name='all-booking'),

    # CATEGORY
    path('api/admin/category/', AdminPackageCategoryAPIView.as_view(), name='category'),
    path('api/admin/category/<int:pk>/', AdminPackageCategoryAPIView.as_view(), name='category'),

    # SUB CATEGORY
    path('api/admin/sub-category/', AdminPackageSubCategoryAPIView.as_view(), name='sub-category'),
    path('api/admin/sub-category/<int:pk>/', AdminPackageSubCategoryAPIView.as_view(), name='sub-category'),

    path('api/admin/commission-slabs/', AdminCommissionSlabListCreateAPIView.as_view(), name='slab-list-create'),
    path('api/admin/commission-slabs/<int:pk>/', AdminCommissionSlabDetailAPIView.as_view(), name='slab-detail'),
    path('api/admin/commissions/', TotalAdminCommission.as_view(), name='commission-list'),

    # 
    path('api/admin/vendor-summary/', AdminVendorOverview.as_view(), name='admin-vendor-summary'),

    path('api/admin/bookings/',AllBookingsAPI.as_view(),name='allbookings'),
    path('api/admin/booking-detail/<str:booking_type>/<int:booking_id>/',BookingDetails.as_view(),name='allbookings'),

    # RECENT USERS
    path('api/admin/recent-users/', RecentUsersAPIView.as_view(), name='recent-users'),

    # TOP VENDORS
    path('api/admin/top-vendors/', TopVendorsAPIView.as_view(), name='top-vendors'),

    #USER SINGLE DATA
    path('api/admin/user/<int:user_id>/', SingleUserAPIView.as_view(), name='single-user'),

    path('api/admin/dashbord-count', DashboardStatsAPIView.as_view(), name='dashboard-count'),

    # RECENT APPROVED BOOKING
    path('api/admin/recent-approved-booking', RecentApprovedBookingsAPIView.as_view(), name='recent-approved'),

    # DASHBOARD REVENUE
    path('api/admin/dashboard/revenu', RevenueGraphView.as_view(), name='DASHBOARD-REVENUE'),
    
    path('api/admin/reviews/', ListAllReviewsAPIView.as_view(), name='list-all-reviews'),

    path('api/admin/combined-bookings/', CombinedBookingsAPIView.as_view(), name='combined-bookings'),

    path('api/admin/payment-details/', PaymentDetailsAPIView.as_view(), name='payment-details'),

    path('api/admin/booking-details/<str:booking_type>/<int:booking_id>/', SingleBookingDetailAPIView.as_view(), name='single-booking-detail'),
    path('api/admin/payment-details/<str:booking_type>/<int:booking_id>/', SinglePaymentDetailAPIView.as_view(), name='single-payment-detail'),


    path('api/admin/buses/', BusAdminAPIView.as_view(), name='admin-bus-api'),
    # SINGLE BUS 
    # path('api/admin/bus/<int:bus_id>/', AdminBusDetailAPIView.as_view()),
    path('api/admin/bus/<int:bus_id>/', SingleBusDetailAPIView.as_view(), name='bus-detail'),

    # USER CREATION
    path('api/admin/admin/create-user/', AdminCreateUserAPIView.as_view(), name='admin-create-user'),


    # PACKAGE LISTING
    path('api/admin/packages/', AdminPackageListView.as_view(), name='admin-package-list'),
    path('api/admin/packages/<int:pk>/', AdminPackageDetailView.as_view(), name='admin-package-detail'),



    path('api/admin/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), 
    path('api/admin/users/<int:user_id>/toggle-status/', ToggleUserActiveStatusAPIView.as_view(), name='toggle-user-status'),

] 