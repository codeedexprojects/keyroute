from django.urls import path
from .views import CreateReviewView, ResetPasswordView, SendOTPView, UserLoginView, UserLogoutView, UserSignupView

urlpatterns = [
    path('signup/', UserSignupView.as_view(), name='user-signup'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('logout/', UserLogoutView.as_view(), name='user-logout'),
    path('forgot-password/send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('forgot-password/reset/', ResetPasswordView.as_view(), name='reset-password'),
    path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
]
