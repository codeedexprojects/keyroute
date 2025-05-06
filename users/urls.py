from django.urls import path
from .views import NormalUserLoginView, NormalUserSignupView, UserLogoutView, UserProfileUpdateView,  VerifyLoginOTPView, VerifySignupOTPView,FavouriteAPIView,ListFavourites, GetReferralCodeView,WalletDetailView,ReferralDetailView

urlpatterns = [
    path("signup/", NormalUserSignupView.as_view(), name="user-signup"),
    path("verify-signup/", VerifySignupOTPView.as_view(), name="verify-signup"),

    path("login/", NormalUserLoginView.as_view(), name="user-login"),
    path("verify-login/", VerifyLoginOTPView.as_view(), name="verify-login"),

    path('logout/', UserLogoutView.as_view(), name='user-logout'),

    # path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    
    path('profile/', UserProfileUpdateView.as_view(), name='user-profile'),

    path('favourites/', FavouriteAPIView.as_view(), name='favourite-api'),

    path('list-favourite/<str:bus_or_package>/',ListFavourites.as_view(),name='list-favourite'),

    path('get-referral-code/', GetReferralCodeView.as_view(), name='get-referral-code'),

    path('wallet/', WalletDetailView.as_view(), name='wallet-detail'),
    path('referral/', ReferralDetailView.as_view(), name='referral-detail'),
]
