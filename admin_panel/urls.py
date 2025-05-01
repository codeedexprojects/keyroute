from django.urls import path
from admin_panel.views import *

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

    # VENODR CREATING AND LISING
    path('api/admin/create-vendor/', AdminCreateVendorAPIView.as_view(), name='admin-create-vendor'),
    path('api/admin/vendors/list/', AdminCreateVendorAPIView.as_view(), name='admin-create-vendor'),

    # VENDOR SINGLE DATA
    path('api/admin/vendors/<int:vendor_id>/', AdminVendorDetailAPIView.as_view(), name='admin-vendor-detail'),

    # SINGLE VENDOR BUS LIST
    path('api/admin/vendors/<int:vendor_id>/buses/', AdminVendorBusListAPIView.as_view()),

    path('api/admin/bus/<int:bus_id>/', AdminBusDetailAPIView.as_view()),

    # PACKAGE LISTING AND SINGLE DETAILS
    path('api/admin/vendor/<int:vendor_id>/packages/', AdminVendorPackageListAPIView.as_view()),
    path('api/admin/vendor/package/<int:package_id>/', AdminPackageDetailAPIView.as_view()),


    # CATEGORY
    path('api/admin/categories/', PackageCategoryListAPIView.as_view()),

    # NORMAL USER CREATING
    path('api/admin/create-user/', AdminCreateUserView.as_view(), name='admin-create-user'),

    #Advertisement
    path('api/admin/sections/create/', AllSectionsCreateView.as_view(), name='create-sections'),

    # EXPLORE
    path('api/admin/explore/create/', ExploreSectionCreateView.as_view(), name='create-explore-section'),

    # EXPLORE LISTING
    path('explore/list/', ExploreSectionListView.as_view(), name='explore-list'),


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



    # RECENT USERS
    path('api/admin/recent-users/', RecentUsersAPIView.as_view(), name='recent-users'),

    # TOP VENDORS
    path('api/admin/top-vendors/', TopVendorsAPIView.as_view(), name='top-vendors'),

    #USER SINGLE DATA
    path('api/admin/user/<int:user_id>/', SingleUserAPIView.as_view(), name='single-user'),



    path('api/admin/dashbord-count', DashboardStatsAPIView.as_view(), name='dashboard-count'),

    # RECENT APPROVED BOOKING
    path('api/admin/recent-approved-booking', RecentApprovedBookingsAPIView.as_view(), name='recent-approved')





    
] 