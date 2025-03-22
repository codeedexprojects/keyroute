from django.urls import path
from .views import *

urlpatterns = [
   path('vendor/signup/', VendorSignupAPIView.as_view(), name='vendor-signup'),
]
