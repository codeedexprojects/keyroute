from django.db.models import Count, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import BusReview, PackageReview
from .serializers import BusReviewSerializer, PackageReviewSerializer
from vendors.models import Bus, Package
from bookings.models import BusBooking, PackageBooking


class BusReviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        bus_id = request.data.get("bus_id")
        rating = request.data.get("rating")
        comment = request.data.get("comment", "")

        if not bus_id or not rating:
            return Response({"error": "Bus ID and Rating are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            bus = Bus.objects.get(id=bus_id)
            
            if BusReview.objects.filter(user=user, bus=bus).exists():
                return Response({"error": "You have already reviewed this bus."}, status=status.HTTP_400_BAD_REQUEST)

            completed_booking = BusBooking.objects.filter(
                user=user, 
                bus=bus, 
                trip_status='completed'
            ).exists()

            if not completed_booking:
                return Response(
                    {"error": "You can only review after completing the trip."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            review = BusReview.objects.create(user=user, bus=bus, rating=rating, comment=comment)
            serializer = BusReviewSerializer(review)

            return Response(
                {"message": "Review submitted successfully.", "review": serializer.data},
                status=status.HTTP_201_CREATED
            )

        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=status.HTTP_404_NOT_FOUND)
    
    def get(self, request, bus_id=None):
        if not bus_id:
            return Response({"error": "Bus ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            bus = Bus.objects.get(id=bus_id)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found"}, status=status.HTTP_404_NOT_FOUND)

        reviews = BusReview.objects.filter(bus=bus).order_by('-created_at')

        rating_breakdown = reviews.values("rating").annotate(count=Count("rating")).order_by("-rating")
        rating_summary = {str(int(rating["rating"])) + "★": rating["count"] for rating in rating_breakdown}

        average_rating = reviews.aggregate(average=Avg("rating"))["average"] or 0.0

        review_serializer = BusReviewSerializer(reviews, many=True)

        response_data = {
            "bus_name": bus.bus_name,
            "average_rating": round(average_rating, 1),
            "total_reviews": reviews.count(),
            "rating_breakdown": rating_summary,
            "reviews": review_serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class PackageReviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        package_id = request.data.get("package_id")
        rating = request.data.get("rating")
        comment = request.data.get("comment", "")

        if not package_id or not rating:
            return Response({"error": "Package ID and Rating are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            package = Package.objects.get(id=package_id)
            
            if PackageReview.objects.filter(user=user, package=package).exists():
                return Response({"error": "You have already reviewed this package."}, status=status.HTTP_400_BAD_REQUEST)

            completed_booking = PackageBooking.objects.filter(
                user=user, 
                package=package, 
                trip_status='completed'
            ).exists()

            if not completed_booking:
                return Response(
                    {"error": "You can only review after completing the trip."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            review = PackageReview.objects.create(user=user, package=package, rating=rating, comment=comment)
            serializer = PackageReviewSerializer(review)

            return Response(
                {"message": "Review submitted successfully.", "review": serializer.data},
                status=status.HTTP_201_CREATED
            )

        except Package.DoesNotExist:
            return Response({"error": "Package not found."}, status=status.HTTP_404_NOT_FOUND)
    
    def get(self, request, package_id=None):
        if not package_id:
            return Response({"error": "Package ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            return Response({"error": "Package not found"}, status=status.HTTP_404_NOT_FOUND)

        reviews = PackageReview.objects.filter(package=package).order_by('-created_at')

        rating_breakdown = reviews.values("rating").annotate(count=Count("rating")).order_by("-rating")
        rating_summary = {str(int(rating["rating"])) + "★": rating["count"] for rating in rating_breakdown}

        average_rating = reviews.aggregate(average=Avg("rating"))["average"] or 0.0

        review_serializer = PackageReviewSerializer(reviews, many=True)

        response_data = {
            "package_name": package.places,
#             "package_name": package,
            "average_rating": round(average_rating, 1),
            "total_reviews": reviews.count(),
            "rating_breakdown": rating_summary,
            "reviews": review_serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)