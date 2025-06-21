from django.urls import path
from .views import (UserLogoutView, UserProfileAPIView,  AuthenticationView, 
                    VerifyOTPView,FavouriteAPIView,ListFavourites, GetReferralCodeView,
                    GetWalletView,OngoingReferralsView,ReferralHistoryView,
                    SightDetailView,ExperienceView,ExperienceDetailView,RemoveFavouriteAPIView,SeasonTimeDetailView,
                    SeasonTimeView,SightView,GreetingAPIView,ResendOTPView,
                    SimilarExperienceView,LimitedDealListAPIView,GetLocationAPIView,FirebaseGoogleAuthView,DeleteUserAccountView,UpdateDistrictAPIView)

urlpatterns = [
    path('auth/', AuthenticationView.as_view(), name='authentication'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('google-auth/', FirebaseGoogleAuthView.as_view(), name='google-auth'),


    # path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    
    path('profile/', UserProfileAPIView.as_view(), name='user-profile'),

    path('favourites/', FavouriteAPIView.as_view(), name='favourite-api'),
    path('favourites/remove/', RemoveFavouriteAPIView.as_view(), name='favourite-api-remove'),

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

    path('sights/<int:sight_id>/similar-experiences/<int:exclude_experience_id>/', SimilarExperienceView.as_view(), name='similar-experiences'),

    path('limited-deals/', LimitedDealListAPIView.as_view(), name='limited-deal-list'),

    path('get-locations/',GetLocationAPIView.as_view(),name="get-locations"),

    path('user/delete-account/', DeleteUserAccountView.as_view(), name='delete-user-account'),
    path('delete-account/', DeleteUserAccountView.as_view(), name='delete-user-account'),

    path('update-district/', UpdateDistrictAPIView.as_view(), name='update-district'),
]