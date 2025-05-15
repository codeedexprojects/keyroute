from django.urls import path
from .views import ReviewView,AppReviewView

urlpatterns = [
    path('reviews/booking/',ReviewView.as_view(),name="booking-reviews"),

    path('reviews/', AppReviewView.as_view(), name='review-list-create'),
    path('reviews/<int:pk>/', AppReviewView.as_view(), name='review-detail'),
]