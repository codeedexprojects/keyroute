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
from notifications.utils import send_notification
from django.utils.dateparse import parse_date


from .utils import *

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
        serializer = BusSerializer(buses, many=True)
        return Response(serializer.data)

class PackageBookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bookings = PackageBooking.objects.filter(user=request.user)
        serializer = PackageBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = PackageBookingSerializer(data=request.data)
        if serializer.is_valid():
            package = serializer.validated_data['package']
            vendor = package.vendor
            booking_date = serializer.validated_data['start_date']

            if is_vendor_busy(vendor, booking_date):
                return Response({"error": "Vendor is busy on the selected date."}, status=status.HTTP_400_BAD_REQUEST)

            booking = serializer.save(user=request.user)
            
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
                
                package_name = booking.package.name if hasattr(booking.package, 'name') else "Tour package"
                send_notification(
                    user=request.user,
                    message=f"Your booking for {package_name} has been successfully created! Booking ID: {booking.id}"
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
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
        old_status = booking.payment_status
        serializer = PackageBookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            
            if 'payment_status' in request.data and old_status != booking.payment_status:
                send_notification(
                    user=request.user,
                    message=f"Your package booking #{pk} status has been updated to: {booking.payment_status}"
                )
                
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BusBookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bookings = BusBooking.objects.filter(user=request.user)
        serializer = BusBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = BusBookingSerializer(data=request.data)
        if serializer.is_valid():
            bus = serializer.validated_data['bus']
            vendor = bus.vendor
            booking_date = serializer.validated_data['start_date']

            if is_vendor_busy(vendor, booking_date):
                return Response({"error": "Vendor is busy on the selected date."}, status=status.HTTP_400_BAD_REQUEST)

            booking = serializer.save(user=request.user)
            
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
                
                bus_name = booking.bus.name if hasattr(booking.bus, 'name') else "Bus"
                route_info = f"from {booking.bus.from_location} to {booking.bus.to_location}" if hasattr(booking.bus, 'from_location') and hasattr(booking.bus, 'to_location') else ""
                
                send_notification(
                    user=request.user,
                    message=f"Your bus booking for {bus_name} {route_info} has been confirmed! Booking ID: {booking.id}"
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
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
        old_status = booking.payment_status
        serializer = BusBookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            
            if 'payment_status' in request.data and old_status != booking.payment_status:
                send_notification(
                    user=request.user,
                    message=f"Your bus booking #{pk} status has been updated to: {booking.payment_status}"
                )
                
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Traveler Views
class TravelerCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TravelerCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            traveler = serializer.save()
            
            if traveler.package_booking:
                booking = traveler.package_booking
                booking_type = "package"
            elif traveler.bus_booking:
                booking = traveler.bus_booking
                booking_type = "bus"
            else:
                booking_type = "unknown"
            
            send_notification(
                user=request.user,
                message=f"New traveler {traveler.first_name} {traveler.last_name} has been added to your {booking_type} booking"
            )
            
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
            updated_traveler = serializer.save()
            
            send_notification(
                user=request.user,
                message=f"Traveler information for {updated_traveler.first_name} {updated_traveler.last_name} has been updated"
            )
            
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        traveler = self.get_object(pk, request.user)
        traveler_name = f"{traveler.first_name} {traveler.last_name}"
        
        if traveler.package_booking:
            booking = traveler.package_booking
            traveler.delete()
            booking.total_travelers = booking.travelers.count()
            booking.save()
            
            send_notification(
                user=request.user,
                message=f"Traveler {traveler_name} has been removed from your package booking"
            )
        else:
            booking = traveler.bus_booking
            traveler.delete()
            
            send_notification(
                user=request.user,
                message=f"Traveler {traveler_name} has been removed from your bus booking"
            )
        
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
            print(vendor.user)
            
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
            serializer = PackageBookingSerializer(package_bookings, many=True)
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
        

class CancelBookingView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, booking_type):
        booking_id = request.data.get('booking_id')
        cancellation_reason = request.data.get('cancellation_reason')
        
        if not booking_type or not booking_id:
            return Response(
                {"error": "Both booking_type and booking_id are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if booking_type not in ['bus', 'package']:
            return Response(
                {"error": "booking_type must be either 'bus' or 'package'"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if booking_type == 'bus':
                booking = BusBooking.objects.get(id=booking_id)
                serializer_class = BusBookingSerializer
            else:
                booking = PackageBooking.objects.get(id=booking_id)
                serializer_class = PackageBookingSerializer
                
            if booking.user != request.user:
                return Response(
                    {"error": "You do not have permission to cancel this booking"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
                
            if booking.payment_status == 'cancelled':
                return Response(
                    {"error": "This booking is already cancelled"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            booking.payment_status = 'cancelled'
            booking.cancelation_reason = cancellation_reason
            booking.save()

            send_notification(
                user=request.user,
                message=f"Your booking with ID {booking_id} has been successfully canceled."
            )

            
            serializer = serializer_class(booking)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except (BusBooking.DoesNotExist, PackageBooking.DoesNotExist):
            return Response(
                {"error": f"{booking_type.capitalize()} booking with id {booking_id} does not exist"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        



class BookingFilterByDate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_type, date):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response(
                {"detail": "Unauthorized: Only vendors can access this data."},
                status=status.HTTP_403_FORBIDDEN
            )

        parsed_date = parse_date(date)
        if not parsed_date:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_datetime = datetime.combine(parsed_date, time.min)
        end_datetime = datetime.combine(parsed_date, time.max)

        if booking_type == 'bus':
            bookings = BusBooking.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                bus__vendor=vendor
            )
            serializer = BusBookingSerializer(bookings, many=True)
        elif booking_type == 'package':
            bookings = PackageBooking.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                package__vendor=vendor
            )
            serializer = PackageBookingSerializer(bookings, many=True)
        elif booking_type == 'all':
            bus_bookings = BusBooking.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                bus__vendor=vendor
            )
            package_bookings = PackageBooking.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                package__vendor=vendor
            )
            
            bus_data = BusBookingSerializer(bus_bookings, many=True).data
            package_data = PackageBookingSerializer(package_bookings, many=True).data
            
            return Response({
                "bus_bookings": bus_data,
                "package_bookings": package_data
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Invalid booking type. Must be 'bus', 'package', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(serializer.data, status=status.HTTP_200_OK)