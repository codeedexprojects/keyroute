from django.urls import path
from .views import CreateReviewView, NormalUserLoginView, NormalUserSignupView, ResetPasswordView, SendOTPView,  UserLogoutView, UserProfileUpdateView,  VerifyLoginOTPView, VerifySignupOTPView,FavouriteAPIView

urlpatterns = [
    path("signup/", NormalUserSignupView.as_view(), name="user-signup"),
    path("verify-signup/", VerifySignupOTPView.as_view(), name="verify-signup"),

    path("login/", NormalUserLoginView.as_view(), name="user-login"),
    path("verify-login/", VerifyLoginOTPView.as_view(), name="verify-login"),

    path('logout/', UserLogoutView.as_view(), name='user-logout'),

    path('forgot-password/send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('forgot-password/reset/', ResetPasswordView.as_view(), name='reset-password'),

    path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    
    path('user/profile/', UserProfileUpdateView.as_view(), name='user-profile'),

    path('favourites/', FavouriteAPIView.as_view(), name='favourite-api'),
]
