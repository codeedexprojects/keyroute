from django.shortcuts import render
from django.db.models import Count, Avg
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import BusReview, Bus
from .serializers import BusReviewSerializer
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# Create your views here.
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Only logged-in users can post reviews
def post_review(request):
    """
    API to submit a review after completing the session.
    """
    user = request.user
    bus_id = request.data.get("bus_id")
    rating = request.data.get("rating")
    comment = request.data.get("comment", "")

    # Validate required fields
    if not bus_id or not rating:
        return Response({"error": "Bus ID and Rating are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        bus = Bus.objects.get(id=bus_id)

        # Check if the user has already reviewed this bus
        if BusReview.objects.filter(user=user, bus=bus).exists():
            return Response({"error": "You have already reviewed this bus."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the user has completed a session (Dummy Check)
        # TODO: Implement logic to verify if the user has completed the session
        session_completed = True  # Change this based on your business logic

        if not session_completed:
            return Response({"error": "You can only review after completing the session."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create and save review
        review = BusReview.objects.create(user=user, bus=bus, rating=rating, comment=comment)
        serializer = BusReviewSerializer(review)

        return Response({"message": "Review submitted successfully.", "review": serializer.data},
                        status=status.HTTP_201_CREATED)

    except Bus.DoesNotExist:
        return Response({"error": "Bus not found."}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(["GET"])
def bus_reviews(request, bus_id):
    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        return Response({"error": "Bus not found"}, status=404)

    reviews = BusReview.objects.filter(bus=bus)

    # Calculate rating breakdown
    rating_breakdown = reviews.values("rating").annotate(count=Count("rating")).order_by("-rating")
    rating_summary = {str(rating["rating"]) + "★": rating["count"] for rating in rating_breakdown}

    # Calculate overall average rating
    average_rating = reviews.aggregate(average=Avg("rating"))["average"] or 0.0

    review_serializer = BusReviewSerializer(reviews, many=True)

    response_data = {
        "bus_name": bus.bus_name,
        "average_rating": round(average_rating, 1),
        "total_reviews": reviews.count(),
        "rating_breakdown": rating_summary,
        "reviews": review_serializer.data
    }

    return Response(response_data, status=200)
