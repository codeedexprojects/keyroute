from django.urls import path
from .views import (UserLogoutView, UserProfileAPIView,  AuthenticationView, 
                    VerifyOTPView,FavouriteAPIView,ListFavourites, GetReferralCodeView,
                    GetWalletView,OngoingReferralsView,ReferralHistoryView,
                    SightDetailView,ExperienceView,ExperienceDetailView,SeasonTimeDetailView,SeasonTimeView,SightView,GreetingAPIView,ResendOTPView)

urlpatterns = [
    path('auth/', AuthenticationView.as_view(), name='authentication'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('logout/', UserLogoutView.as_view(), name='logout'),

    # path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    
    path('profile/', UserProfileAPIView.as_view(), name='user-profile'),

    path('favourites/', FavouriteAPIView.as_view(), name='favourite-api'),

    path('list-favourite/<str:bus_or_package>/',ListFavourites.as_view(),name='list-favourite'),

    path('get-referral-code/', GetReferralCodeView.as_view(), name='get-referral-code'),

    path('get-wallet/',GetWalletView.as_view(),name='get-wallet'),

    path('referrals/ongoing/',OngoingReferralsView.as_view(), name='ongoing-referrals'),
    path('referrals/history/',ReferralHistoryView.as_view(), name='referral-history'),

    path('sights/', SightView.as_view(), name='sight-list'),
    path('sights/<int:pk>/', SightDetailView.as_view(), name='sight-detail'),

    path('sights/<int:sight_id>/experiences/', ExperienceView.as_view(), name='experience-list'),
    
    path('experiences/<int:pk>/', ExperienceDetailView.as_view(), name='experience-detail'),
    path('sights/<int:sight_id>/seasons/', SeasonTimeView.as_view(), name='season-list'),
    path('seasons/<int:pk>/', SeasonTimeDetailView.as_view(), name='season-detail'),

    path('greeting/', GreetingAPIView.as_view(), name='greeting'),
]