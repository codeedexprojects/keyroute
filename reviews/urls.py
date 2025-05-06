from django.urls import path
from .views import BusReviewView, PackageReviewView

urlpatterns = [
    # Bus review endpoints
    path('reviews/bus/', BusReviewView.as_view(), name='post_bus_review'),
    path('reviews/bus/<int:bus_id>/', BusReviewView.as_view(), name='get_bus_reviews'),
    
    # Package review endpoints
    path('api/vendorreviews/package/', PackageReviewView.as_view(), name='post_package_review'),
    path('reviews/package/<int:package_id>/', PackageReviewView.as_view(), name='get_package_reviews'),
]