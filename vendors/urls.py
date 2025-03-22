from django.urls import path
from .views import *

urlpatterns = [
   path('api/vendor/signup/', VendorSignupAPIView.as_view(), name='vendor-signup'),
   path('api/vendor/login/', LoginAPIView.as_view(), name='vendor_login'),
   path('api/vendor/forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot_password'),
   path('api/vendor/logout/', LogoutAPIView.as_view(), name='logout'),
   

]
