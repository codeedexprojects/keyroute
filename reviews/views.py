from django.db.models import Count, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import BusReview, PackageReview,AppReview
from .serializers import BusReviewSerializer, PackageReviewSerializer,AppReviewSerializer
from vendors.models import Bus, Package
from bookings.models import BusBooking, PackageBooking
from rest_framework_simplejwt.authentication import JWTAuthentication
from admin_panel.models import *
from .serializers import ReviewStatsSerializer


class ReviewView(APIView):
    """
    Unified API view for handling both bus and package reviews.
    Supports creating and retrieving reviews for both types.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        item_type = request.data.get("item_type")
        item_id = request.data.get("item_id")
        rating = request.data.get("rating")
        comment = request.data.get("comment", "")

        if not item_type or not item_id or not rating:
            return Response(
                {"error": "Item type, Item ID, and Rating are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if item_type not in ['bus', 'package']:
            return Response(
                {"error": "Item type must be either 'bus' or 'package'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if item_type == 'bus':
                item = Bus.objects.get(id=item_id)
                
                # Check if user already reviewed this bus
                if BusReview.objects.filter(user=user, bus=item).exists():
                    return Response(
                        {"error": "You have already reviewed this bus."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if user completed a booking with this bus
                completed_booking = BusBooking.objects.filter(
                    user=user, 
                    bus=item, 
                    trip_status='completed'
                ).exists()
                
                if not completed_booking:
                    return Response(
                        {"error": "You can only review after completing the trip."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create the review
                review = BusReview.objects.create(user=user, bus=item, rating=rating, comment=comment)
                serializer = BusReviewSerializer(review, context={'request': request})
                
            else:  # item_type == 'package'
                item = Package.objects.get(id=item_id)
                
                # Check if user already reviewed this package
                if PackageReview.objects.filter(user=user, package=item).exists():
                    return Response(
                        {"error": "You have already reviewed this package."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if user completed a booking with this package
                completed_booking = PackageBooking.objects.filter(
                    user=user, 
                    package=item, 
                    trip_status='completed'
                ).exists()
                
                if not completed_booking:
                    return Response(
                        {"error": "You can only review after completing the trip."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create the review
                review = PackageReview.objects.create(user=user, package=item, rating=rating, comment=comment)
                serializer = PackageReviewSerializer(review, context={'request': request})
            
            return Response(
                {"message": f"{item_type.capitalize()} review submitted successfully.", "review": serializer.data},
                status=status.HTTP_201_CREATED
            )
            
        except (Bus.DoesNotExist, Package.DoesNotExist):
            return Response(
                {"error": f"{item_type.capitalize()} not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get(self, request):
        item_type = request.query_params.get("item_type")
        item_id = request.query_params.get("item_id")
        
        if not item_type or not item_id:
            return Response(
                {"error": "Item type and Item ID are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if item_type not in ['bus', 'package']:
            return Response(
                {"error": "Item type must be either 'bus' or 'package'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            if item_type == 'bus':
                item = Bus.objects.get(id=item_id)
                reviews = BusReview.objects.filter(bus=item).order_by('-created_at')
                review_serializer = BusReviewSerializer(reviews, many=True, context={'request': request})
                item_name = item.bus_name
                
            else:  # item_type == 'package'
                item = Package.objects.get(id=item_id)
                reviews = PackageReview.objects.filter(package=item).order_by('-created_at')
                review_serializer = PackageReviewSerializer(reviews, many=True, context={'request': request})
                item_name = item.places
            
            # Calculate rating breakdown and average
            rating_breakdown = reviews.values("rating").annotate(count=Count("rating")).order_by("-rating")
            rating_summary = {str(int(rating["rating"])) + "★": rating["count"] for rating in rating_breakdown}
            average_rating = reviews.aggregate(average=Avg("rating"))["average"] or 0.0
            
            response_data = {
                "item_type": item_type,
                "item_name": item_name,
                "average_rating": round(average_rating, 1),
                "total_reviews": reviews.count(),
                "rating_breakdown": rating_summary,
                "reviews": review_serializer.data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (Bus.DoesNotExist, Package.DoesNotExist):
            return Response(
                {"error": f"{item_type.capitalize()} not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )    


class VendorAllReviewsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # def get(self, request):
    #     try:
    #         vendor = Vendor.objects.get(user=request.user)
    #     except Vendor.DoesNotExist:
    #         return Response({"error": "Vendor profile not found."}, status=status.HTTP_404_NOT_FOUND)

    #     vendor_packages = Package.objects.filter(vendor=vendor)
    #     vendor_buses = Bus.objects.filter(vendor=vendor)

    #     package_reviews = PackageReview.objects.filter(package__in=vendor_packages).order_by('-created_at')
    #     bus_reviews = BusReview.objects.filter(bus__in=vendor_buses).order_by('-created_at')

    #     package_serializer = PackageReviewSerializer(package_reviews, many=True)
    #     bus_serializer = BusReviewSerializer(bus_reviews, many=True)

    #     return Response({
    #         "vendor": {
    #             "name": vendor.user.name,
    #             "mobile": vendor.user.mobile
    #         },
    #         "total_package_reviews": package_reviews.count(),
    #         "total_bus_reviews": bus_reviews.count(),
    #         "package_reviews": package_serializer.data,
    #         "bus_reviews": bus_serializer.data,
    #     }, status=status.HTTP_200_OK)



    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor profile not found."}, status=status.HTTP_404_NOT_FOUND)

        vendor_packages = Package.objects.filter(vendor=vendor)
        vendor_buses = Bus.objects.filter(vendor=vendor)

        package_reviews = PackageReview.objects.filter(package__in=vendor_packages).order_by('-created_at')
        bus_reviews = BusReview.objects.filter(bus__in=vendor_buses).order_by('-created_at')

        package_serializer = PackageReviewSerializer(package_reviews, many=True)
        bus_serializer = BusReviewSerializer(bus_reviews, many=True)

        all_reviews = sorted(
            package_serializer.data + bus_serializer.data,
            key=lambda r: r.get('created_at', ''),
            reverse=True
        )

        return Response({
            "vendor": {
                "name": vendor.user.name,
                "mobile": vendor.user.mobile
            },
            "total_reviews": len(all_reviews),
            "reviews": all_reviews
        }, status=status.HTTP_200_OK)












class AppReviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = AppReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, pk=None):
        if pk:
            try:
                review = AppReview.objects.get(pk=pk)
                serializer = AppReviewSerializer(review)
                return Response(serializer.data)
            except AppReview.DoesNotExist:
                return Response({"detail": "Review not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            reviews = AppReview.objects.all().order_by("-created_at")
            total_reviews = reviews.count()
            average_rating = reviews.aggregate(avg=Avg("rating"))["avg"] or 0.0
            
            stats_data = {
                "total_reviews": total_reviews,
                "average_rating": round(average_rating, 1),
                "reviews": reviews
            }

            serializer = ReviewStatsSerializer(stats_data)
            return Response(serializer.data)
