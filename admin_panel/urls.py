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


    path('api/admin/vendor/<int:vendor_id>/packages/', AdminVendorPackageListAPIView.as_view()),
    path('api/admin/vendor/package/<int:package_id>/', AdminPackageDetailAPIView.as_view()),
    




] 


