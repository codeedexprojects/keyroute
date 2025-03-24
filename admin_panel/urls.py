from django.urls import path
from admin_panel.views import *

urlpatterns = [
    path('api/admin/login/', AdminLoginAPIView.as_view(), name='admin-login'),
    
    # VENDOR
    path('api/admin/vendors/list', VendorListAPIView.as_view(), name='vendor-list'),
    path('api/admin/vendor/<int:vendor_id>/', VendorDetailAPIView.as_view(), name='vendor-detail'),

    # COUNT
    path('api/admin/vendor/count/', VendorCountAPIView.as_view(), name='vendor-count'),
    path('api/admin/user/count/', UserCountAPIView.as_view(), name='user-count'),

    # RECENT USERS
    path('api/admin/recent-user/', RecentlyJoinedUsersAPIView.as_view(), name='recent-users'),




]


