from django.urls import path
from admin_panel.views import *

urlpatterns = [
    path('api/admin/vendors/list', VendorListAPIView.as_view(), name='vendor-list'),
    path('api/admin/login/', AdminLoginAPIView.as_view(), name='admin-login'),
]
