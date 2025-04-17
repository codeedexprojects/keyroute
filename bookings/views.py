from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from .models import PackageBooking, BusBooking, Travelers
from .serializers import (
    PackageBookingSerializer, BusBookingSerializer, 
    TravelerSerializer, TravelerCreateSerializer
)
from vendors.models import Package, Bus
from vendors.serializers import PackageSerializer, BusSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from admin_panel.models import Vendor
from users.models import Favourite

class PackageListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        packages = Package.objects.all()
        serializer = PackageSerializer(packages, many=True)
        return Response(serializer.data)

class BusListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        buses = Bus.objects.all()
        
        if request.user.is_authenticated:
            # Get the user's favorite buses
            favorite_bus_ids = Favourite.objects.filter(
                user=request.user
            ).values_list('bus_id', flat=True)
            
            # Update is_favourited field for each bus before serialization
            for bus in buses:
                bus.is_favourited = bus.id in favorite_bus_ids
        
        serializer = BusSerializer(buses, many=True)
        return Response(serializer.data)

# Package Booking Views
class PackageBookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bookings = PackageBooking.objects.filter(user=request.user)
        serializer = PackageBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = PackageBookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save(user=request.user)
            
            # Create a traveler entry for the user who's making the booking
            traveler_data = {
                "first_name": request.user.name or request.user.username,
                "last_name": '',
                "gender": request.data.get('gender', ''),
                "place": request.data.get('place', ''),
                "dob": request.data.get('dob', None),
                "id_proof": request.data.get('id_proof', None),
                "email": request.user.email,
                "mobile": str(request.user),
                "city": request.data.get('city', ''),
                "booking_type": "package",
                "booking_id": booking.id
            }
            
            travelerSerializer = TravelerCreateSerializer(data=traveler_data)
            if travelerSerializer.is_valid():
                travelerSerializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                # If traveler creation fails, delete the booking
                booking.delete()
                return Response(travelerSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PackageBookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        return get_object_or_404(PackageBooking, pk=pk, user=user)
    
    def get(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = PackageBookingSerializer(booking)
        return Response(serializer.data)
    
    def put(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = PackageBookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        booking = self.get_object(pk, request.user)
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Bus Booking Views
class BusBookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bookings = BusBooking.objects.filter(user=request.user)
        serializer = BusBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = BusBookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save(user=request.user)
            
            # Create a traveler entry for the user who's making the booking
            traveler_data = {
                "first_name": request.user.name or request.user.username,
                "last_name": '',
                "gender": request.data.get('gender', ''),
                "place": request.data.get('place', ''),
                "dob": request.data.get('dob', None),
                "id_proof": request.data.get('id_proof', None),
                "email": request.user.email,
                "mobile": request.data.get('mobile', ''),
                "city": request.data.get('city', ''),
                "booking_type": "bus",
                "booking_id": booking.id
            }
            
            travelerSerializer = TravelerCreateSerializer(data=traveler_data)
            if travelerSerializer.is_valid():
                travelerSerializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                # If traveler creation fails, delete the booking
                booking.delete()
                return Response(travelerSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusBookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        return get_object_or_404(BusBooking, pk=pk, user=user)
    
    def get(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = BusBookingSerializer(booking)
        return Response(serializer.data)
    
    def put(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = BusBookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        booking = self.get_object(pk, request.user)
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Traveler Views
class TravelerCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TravelerCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            # The validation in TravelerCreateSerializer will ensure correct booking association
            traveler = serializer.save()
            
            # Return the standard traveler serializer for consistency in the response
            return Response(TravelerSerializer(traveler).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PackageBookingTravelersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, booking_id):
        booking = get_object_or_404(PackageBooking, pk=booking_id, user=request.user)
        travelers = booking.travelers.all()
        serializer = TravelerSerializer(travelers, many=True)
        return Response(serializer.data)

class BusBookingTravelersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, booking_id):
        booking = get_object_or_404(BusBooking, pk=booking_id, user=request.user)
        travelers = booking.travelers.all()
        serializer = TravelerSerializer(travelers, many=True)
        return Response(serializer.data)

class TravelerDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        traveler = get_object_or_404(Travelers, pk=pk)
        
        # Check permissions - user must own the booking associated with this traveler
        if (traveler.bus_booking and traveler.bus_booking.user != user) or \
           (traveler.package_booking and traveler.package_booking.user != user):
            self.permission_denied(self.request)
            
        return traveler
    
    def get(self, request, pk):
        traveler = self.get_object(pk, request.user)
        serializer = TravelerSerializer(traveler)
        return Response(serializer.data)
    
    def put(self, request, pk):
        traveler = self.get_object(pk, request.user)
        serializer = TravelerSerializer(traveler, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        traveler = self.get_object(pk, request.user)
        
        # Update the total_travelers count if this is a package booking
        if traveler.package_booking:
            booking = traveler.package_booking
            traveler.delete()
            booking.total_travelers = booking.travelers.count()
            booking.save()
        else:
            traveler.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)

class BookingsByStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, status, booking_type):
        user = request.user
        
        if booking_type == 'package':
            bookings = PackageBooking.objects.filter(payment_status=status, user=user)
            serializer = PackageBookingSerializer(bookings, many=True)
        elif booking_type == 'bus':
            bookings = BusBooking.objects.filter(payment_status=status, user=user)
            serializer = BusBookingSerializer(bookings, many=True)
        else:
            return Response(
                {"error": "Invalid booking type. Use 'package' or 'bus'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return Response(serializer.data)
    
class VendorBusBookingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
            bus_bookings = BusBooking.objects.filter(bus__vendor=vendor).order_by('-created_at')
            serializer = BusBookingSerializer(bus_bookings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"detail": "Unauthorized: Only vendors can access this data."}, status=status.HTTP_403_FORBIDDEN)
        
class VendorPackageBookingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
            package_bookings = PackageBooking.objects.filter(package__vendor=vendor).order_by('-created_at')
            serializer = PackageBooking(package_bookings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"detail": "Unauthorized: Only vendors can access this data."}, status=status.HTTP_403_FORBIDDEN)
        

class VendorBusBookingByStatusAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_status):
        try:
            vendor = Vendor.objects.get(user=request.user)
            bus_bookings = BusBooking.objects.filter(bus__vendor=vendor, payment_status=booking_status).order_by('-created_at')
            serializer = BusBookingSerializer(bus_bookings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"detail": "Unauthorized: Only vendors can access this data."}, status=status.HTTP_403_FORBIDDEN)

        
class VendorPackageBookingByStatusAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_status):
        try:
            vendor = Vendor.objects.get(user=request.user)
            package_bookings = PackageBooking.objects.filter(package__vendor=vendor, payment_status=booking_status).order_by('-created_at')
            serializer = PackageBookingSerializer(package_bookings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            return Response({"detail": "Unauthorized: Only vendors can access this data."}, status=status.HTTP_403_FORBIDDEN)