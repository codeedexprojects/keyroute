from django.urls import path
from .views import bus_reviews, post_review

urlpatterns = [
    path("<int:bus_id>/reviews/", bus_reviews, name="bus-reviews"),
    path("post-review/", post_review, name="post-review"),
]
