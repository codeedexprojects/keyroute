from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from .models import PackageBooking, BusBooking, Travelers, UserBusSearch
from .serializers import (
    PackageBookingSerializer, BusBookingSerializer, 
    TravelerSerializer, TravelerCreateSerializer
)
from vendors.models import Package, Bus
from vendors.serializers import BusSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from admin_panel.models import Vendor
from users.models import Favourite
from notifications.utils import send_notification
from django.utils.dateparse import parse_date
from datetime import datetime, time
from django.db.models import Q
from rest_framework import status as http_status
from itertools import chain
from vendors.models import PackageCategory,PackageSubCategory
from vendors.serializers import PackageCategorySerializer,PackageSubCategorySerializer
from .serializers import (PackageFilterSerializer,PackageBookingUpdateSerializer,BusFilterSerializer,
                          ListPackageSerializer,ListingUserPackageSerializer,
                          UserBusSearchSerializer,SinglePackageBookingSerilizer,
                          SingleBusBookingSerializer,PackageSerializer,PopularBusSerializer,BusListingSerializer,
                          FooterSectionSerializer,AdvertisementSerializer,BusListResponseSerializer,BusBookingUpdateSerializer,TripStatusUpdateSerializer)
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from .utils import *
from admin_panel.models import FooterSection,Advertisement
from admin_panel.utils import get_admin_commission_from_db,get_advance_amount_from_db
from .models import PackageDriverDetail,BusDriverDetail
from .serializers import PackageDriverDetailSerializer,BusDriverDetailSerializer
from django.db.models import Avg
from .serializers import UserBusSearchStopSerializer
from .utils import BusPriceCalculatorMixin
import razorpay
import hmac
import hashlib
from django.conf import settings
from decimal import Decimal
from .models import BusBooking, PackageBooking, PaymentTransaction
from .serializers import (
    PaymentOrderSerializer, 
    PaymentVerificationSerializer,
    BusBookingSerializer,
    PackageBookingSerializer
)


class PackageListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        category = request.query_params.get('category')
        total_travellers = request.query_params.get('total_travellers')
        search = request.query_params.get('search')

        # Validate required parameters
        if lat is None or lon is None:
            return Response(
                {"error": "Latitude (lat) and Longitude (lon) query parameters are required."},
                status=400
            )

        # Either category or search must be provided
        if not category and not search:
            return Response(
                {"error": "Either 'category' or 'search' parameter must be provided."},
                status=400
            )

        try:
            lat = float(lat)
            lon = float(lon)
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return Response(
                    {"error": "Latitude must be between -90 and 90, and longitude between -180 and 180."},
                    status=400
                )
            user_coords = (lat, lon)

            try:
                geolocator = Nominatim(user_agent="coord-debug")
                location = geolocator.reverse(user_coords, exactly_one=True, timeout=10)
                print(location.address if location else "Invalid coordinates")
            except Exception as e:
                print(f"Geolocation error: {e}")

        except ValueError:
            return Response(
                {"error": "Latitude and longitude must be valid float values."},
                status=400
            )

        # Validate total_travellers if provided (optional parameter)
        travellers_count = None
        if total_travellers is not None:
            try:
                travellers_count = int(total_travellers)
                if travellers_count <= 0:
                    return Response(
                        {"error": "Total travellers must be a positive integer."},
                        status=400
                    )
            except ValueError:
                return Response(
                    {"error": "Total travellers must be a valid integer."},
                    status=400
                )

        # Build query based on provided parameters
        packages = Package.objects.all()
        
        # Apply category filter if provided
        if category:
            packages = packages.filter(sub_category=category)
        
        # Apply search filter if provided
        if search:
            packages = packages.filter(places__icontains=search)
        
        # Check if any packages exist after filtering
        if not packages.exists():
            error_parts = []
            if category:
                error_parts.append(f"category '{category}'")
            if search:
                error_parts.append(f"search '{search}'")
            
            error_message = f"No packages found"
            if error_parts:
                error_message += f" for {' and '.join(error_parts)}"
            
            return Response({"error": error_message}, status=404)

        # Filter packages by location (within 30km)
        nearby_packages = []
        for package in packages:
            if package.buses.exists():  # Check if package has any buses
                # Get buses associated with this package
                buses_with_coords = package.buses.filter(
                    latitude__isnull=False, 
                    longitude__isnull=False
                )
                
                # Check if at least one bus is within range
                is_nearby = False
                has_suitable_capacity = True  # Default to True if no travellers filter
                
                for bus in buses_with_coords:
                    bus_coords = (bus.latitude, bus.longitude)
                    distance_km = geodesic(user_coords, bus_coords).kilometers
                    if distance_km <= 30:
                        is_nearby = True
                        break
                
                # If travellers count is specified, check bus capacity suitability
                if travellers_count is not None and is_nearby:
                    has_suitable_capacity = self._has_suitable_bus_capacity(package, travellers_count)
                
                if is_nearby and has_suitable_capacity:
                    nearby_packages.append(package)

        # Build response message for no results
        if not nearby_packages:
            message_parts = ["No packages found near your location within 30 km"]
            
            if category:
                message_parts.append(f"for category '{category}'")
            if search:
                message_parts.append(f"matching search '{search}'")
            if travellers_count:
                message_parts.append(f"with suitable capacity for {travellers_count} travellers")
            
            message = " ".join(message_parts)
            return Response({"message": message}, status=200)

        # Create a custom serializer context with user location for distance calculation
        context = {
            'request': request,
            'user_location': user_coords,
            'total_travellers': travellers_count
        }
        
        serializer = ListPackageSerializer(nearby_packages, many=True, context=context)
        return Response(serializer.data)

    def _has_suitable_bus_capacity(self, package, required_capacity):
        """
        Check if the package has buses with suitable capacity.
        Returns True if there's a bus with exact capacity or the next available higher capacity.
        """
        # Get all bus capacities for this package
        bus_capacities = list(package.buses.values_list('capacity', flat=True))
        
        if not bus_capacities:
            return False
        
        # Check if there's an exact match
        if required_capacity in bus_capacities:
            return True
        
        # Find the next available higher capacity
        higher_capacities = [cap for cap in bus_capacities if cap > required_capacity]
        
        if higher_capacities:
            # Get the minimum higher capacity
            min_higher_capacity = min(higher_capacities)
            # Allow some reasonable buffer (e.g., within 50% of required capacity)
            capacity_threshold = required_capacity * 1.5
            return min_higher_capacity <= capacity_threshold
        
        return False
    
class SinglePackageListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request,package_id):
        try:
            packages = Package.objects.get(id=package_id)
            serializer = ListingUserPackageSerializer(packages, many=False, context={'request': request})
            return Response(serializer.data)
        except Package.DoesNotExist:
            return Response({"error": "No Pckages Found."}, status=404)

class BusListAPIView(BusPriceCalculatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_search = UserBusSearch.objects.get(user=request.user)
        except UserBusSearch.DoesNotExist:
            return Response({"error": "No bus search data found for this user."}, status=404)

        # Check if destination coordinates are provided
        if not user_search.to_lat or not user_search.to_lon:
            return Response({"message": "Please select destination location"}, status=200)

        user_coords = (user_search.from_lat, user_search.from_lon)

        # Optional debug log for location
        try:
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="bus-locator")
            location = geolocator.reverse(user_coords, exactly_one=True, timeout=10)
            print("User Location:", location.address if location else "Unknown")
        except Exception as e:
            print(f"Geolocation error: {e}")

        search = request.query_params.get('search')

        # Initial queryset
        buses = Bus.objects.filter(latitude__isnull=False, longitude__isnull=False)

        # Filter by seat if provided
        if user_search.seat:
            buses = buses.filter(capacity__gte=user_search.seat)

        # Filter by features
        if user_search.ac:
            buses = buses.filter(features__name__iexact='ac')
        if user_search.pushback:
            buses = buses.filter(features__name__iexact='pushback')

        # Prepare buses with distance information
        buses_with_distance = []

        # If search has value, filter by name only (no location filtering)
        if search:
            buses = buses.filter(bus_name__icontains=search)
            buses_only = list(buses.distinct())
            
            # For search results, calculate distance from user location to each bus
            for bus in buses_only:
                if bus.latitude is not None and bus.longitude is not None:
                    bus_coords = (bus.latitude, bus.longitude)
                    distance_km = geodesic(user_coords, bus_coords).kilometers
                    buses_with_distance.append((bus, distance_km))
                else:
                    # If bus doesn't have coordinates, set distance as None or a high value
                    buses_with_distance.append((bus, None))
        else:
            # No search - apply location-based filtering (within 30 km)
            for bus in buses.distinct():
                if bus.latitude is not None and bus.longitude is not None:
                    bus_coords = (bus.latitude, bus.longitude)
                    distance_km = geodesic(user_coords, bus_coords).kilometers
                    if distance_km <= 30:
                        buses_with_distance.append((bus, distance_km))

            if not buses_with_distance:
                return Response({"message": "No buses found near your location within 30 km."}, status=200)

        if not buses_with_distance:
            return Response({"message": "No buses found matching your criteria."}, status=200)

        # Get sorting parameter
        sort_by = request.query_params.get('sort_by', 'nearest')

        # Get dates and stops data for price calculation
        start_date = user_search.pick_up_date if user_search.pick_up_date else timezone.now().date()
        end_date = user_search.return_date if user_search.return_date else start_date
        
        stops_data = []
        if hasattr(user_search, 'search_stops'):
            search_stops = user_search.search_stops.all().order_by('stop_order')
            for stop in search_stops:
                stops_data.append({
                    'location_name': stop.location_name,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude
                })

        # Apply sorting with unified price calculation
        if sort_by == 'nearest':
            # Sort by distance (handle None distances by putting them at the end)
            buses_with_distance.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
        elif sort_by == 'popular':
            # Filter popular buses and then sort by distance
            buses_with_distance = [(bus, dist) for bus, dist in buses_with_distance if getattr(bus, 'is_popular', False)]
            buses_with_distance.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
        elif sort_by == 'top_rated':
            buses_with_distance.sort(key=lambda x: x[0].bus_reviews.aggregate(avg=Avg('rating'))['avg'] or 0, reverse=True)
        elif sort_by == 'price_low_to_high':
            bus_prices = []
            for bus, dist in buses_with_distance:
                price = self.calculate_comprehensive_trip_price(
                    bus, user_search.from_lat, user_search.from_lon,
                    user_search.to_lat, user_search.to_lon,
                    start_date, end_date, stops_data
                )
                bus_prices.append((bus, dist, price))
            bus_prices.sort(key=lambda x: x[2])
            buses_with_distance = [(bus, dist) for bus, dist, price in bus_prices]
        elif sort_by == 'price_high_to_low':
            bus_prices = []
            for bus, dist in buses_with_distance:
                price = self.calculate_comprehensive_trip_price(
                    bus, user_search.from_lat, user_search.from_lon,
                    user_search.to_lat, user_search.to_lon,
                    start_date, end_date, stops_data
                )
                bus_prices.append((bus, dist, price))
            bus_prices.sort(key=lambda x: x[2], reverse=True)
            buses_with_distance = [(bus, dist) for bus, dist, price in bus_prices]

        # Get the nearest bus distance (first bus after sorting)
        nearest_distance = None
        if buses_with_distance:
            # Find the minimum distance from all buses
            distances = [dist for bus, dist in buses_with_distance if dist is not None]
            if distances:
                nearest_distance = min(distances)

        buses_only = [bus for bus, distance in buses_with_distance]

        response_data = {
            'buses': buses_only,
            'distance_km': round(nearest_distance, 2) if nearest_distance is not None else None
        }

        serializer = BusListResponseSerializer(
            response_data,
            context={
                'request': request, 
                'user_search': user_search
            }
        )
        return Response(serializer.data)
    



class SingleBusListAPIView(APIView):
    """
    Updated Single Bus API View with comprehensive price calculation
    """
    permission_classes = [AllowAny]
    
    def get(self, request, bus_id):
        try:
            bus = Bus.objects.get(id=bus_id)
            serializer = BusListingSerializer(bus, many=False, context={'request': request})
            return Response(serializer.data)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found"}, status=404)
        except Exception as e:
            logging.error(f"Error in SingleBusListAPIView: {str(e)}")
            return Response({"error": "Internal server error"}, status=500)

class PackageBookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = PackageBooking.objects.filter(user=request.user)
        serializer = PackageBookingSerializer(bookings, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        query_data = {
            'start_date': request.query_params.get('start_date'),
            'total_travelers': request.query_params.get('total_travelers'),
            'from_location': request.query_params.get('from_location'),
            'children': request.query_params.get('children'),
            'female': request.query_params.get('female'),
            'male': request.query_params.get('male'),
        }
        data.update(query_data)
        serializer = PackageBookingSerializer(data=data, context={'request': request})

        if serializer.is_valid():
            package = serializer.validated_data['package']
            booking_date = serializer.validated_data['start_date']
            total_travelers = serializer.validated_data.get('total_travelers', 0)

            # Check if package is available for the given dates and travelers
            is_available, availability_message = is_package_available(
                package, booking_date, total_travelers
            )
            
            if not is_available:
                return Response(
                    {"error": f"Package is not available: {availability_message}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Additional check for bus conflicts with existing package bookings
            night_count = package.day_plans.filter(night=True).count()
            total_days = package.days + night_count
            end_date = booking_date + timedelta(days=total_days)

            # Create the booking
            booking = serializer.save(user=request.user)

            # Send notification
            package_name = booking.package.places if hasattr(booking.package, 'places') else "Tour package"
            send_notification(
                user=request.user,
                message=f"Your booking for {package_name} has been successfully created! Booking ID: {booking.booking_id}",
                title="Package Booked",
                data={"message_id": booking.booking_id, "type": "booking"}
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PackageBookingUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, booking_id):
        booking = get_object_or_404(PackageBooking, booking_id=booking_id, user=request.user)
        
        # Use the dedicated update serializer
        serializer = PackageBookingUpdateSerializer(
            booking,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            booking = serializer.save()
            
            package_name = booking.package.name if hasattr(booking.package, 'name') else "Tour package"
            send_notification(
                user=request.user,
                message=f"Your booking for {package_name} has been successfully updated! Booking ID: {booking.booking_id}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PackageBookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        return get_object_or_404(PackageBooking, booking_id=pk, user=user)
    
    def get(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = SinglePackageBookingSerilizer(booking)
        return Response(serializer.data)
    
    def patch(self, request, pk):
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
        bookings = BusBooking.objects.filter(user=request.user).order_by('-created_at')
        serializer = BusBookingSerializer(bookings, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = BusBookingSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                user = request.user
                bus = serializer.validated_data['bus']
                
                # Get user search data for date validation
                try:
                    user_search = UserBusSearch.objects.get(user=user)
                except UserBusSearch.DoesNotExist:
                    return Response(
                        {"error": "Bus search data not found. Please search for buses first."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Determine trip dates
                start_date = user_search.pick_up_date
                end_date = user_search.return_date if user_search.return_date else start_date
                start_time = user_search.pick_up_time
                
                if not start_date:
                    return Response(
                        {"error": "Pickup date is required."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if bus is busy during the trip duration
                is_busy, busy_message = is_bus_busy(
                    bus, start_date, end_date, start_time, None
                )
                
                if is_busy:
                    return Response(
                        {"error": f"Bus is not available: {busy_message}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create booking
                booking = serializer.save(user=user)
                
                # Send notification
                bus_name = booking.bus.bus_name if booking.bus.bus_name else "Bus"
                route_info = f"from {booking.from_location} to {booking.to_location}"
                
                # Add stops info to notification
                stops_info = ""
                if booking.stops.exists():
                    stop_names = [stop.location_name for stop in booking.stops.all()]
                    stops_info = f" with stops at {', '.join(stop_names)}"
                
                send_notification(
                    user=request.user,
                    message=f"Your booking for has been successfully created! Booking ID: {booking.booking_id}",
                    title="Package Booked",
                    data={"message_id": booking.booking_id, "type": "booking"}
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creating bus booking: {str(e)}")
                return Response(
                    {"error": "An error occurred while creating the booking. Please try again."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddStopsAPIView(APIView):
    """API to manage (add/update/delete) user's bus search stops"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Add or update stops for the authenticated user"""
        user = request.user
        stops_data = request.data.get('stops', [])

        # Get or create user search object
        user_search, _ = UserBusSearch.objects.get_or_create(user=user)

        # If stops are not provided, clear all existing stops
        if not stops_data:
            user_search.search_stops.all().delete()
            return Response({
                "message": "All stops cleared since no stops were provided.",
                "stops": []
            }, status=status.HTTP_200_OK)

        # Validate all stops
        for i, stop in enumerate(stops_data):
            if not all(key in stop for key in ['location_name', 'latitude', 'longitude']):
                return Response(
                    {"error": f"Stop {i+1} must contain location_name, latitude, and longitude"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                float(stop['latitude'])
                float(stop['longitude'])
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Stop {i+1} has invalid latitude or longitude"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            # Use transaction to ensure data integrity
            with transaction.atomic():
                # Get existing stops
                existing_stops = list(user_search.search_stops.all().order_by('stop_order'))
                
                # Update or create stops based on stop_order
                for i, stop_data in enumerate(stops_data):
                    stop_order = i + 1
                    
                    # Try to find existing stop with this order
                    existing_stop = next((stop for stop in existing_stops if stop.stop_order == stop_order), None)
                    
                    if existing_stop:
                        # Update existing stop
                        existing_stop.location_name = stop_data['location_name']
                        existing_stop.latitude = float(stop_data['latitude'])
                        existing_stop.longitude = float(stop_data['longitude'])
                        existing_stop.save()
                    else:
                        # Create new stop
                        UserBusSearchStop.objects.create(
                            user_search=user_search,
                            stop_order=stop_order,
                            location_name=stop_data['location_name'],
                            latitude=float(stop_data['latitude']),
                            longitude=float(stop_data['longitude']),
                        )
                
                # Delete any remaining stops that exceed the new count
                if len(existing_stops) > len(stops_data):
                    stops_to_delete = [stop for stop in existing_stops if stop.stop_order > len(stops_data)]
                    for stop in stops_to_delete:
                        stop.delete()

            # Return updated stops
            updated_stops = user_search.search_stops.all().order_by('stop_order')
            serializer = UserBusSearchStopSerializer(updated_stops, many=True)
            return Response({
                "message": "Stops updated successfully",
                "stops": serializer.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error while updating stops: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred while updating stops"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """Get current stops for the authenticated user"""
        user = request.user
        try:
            user_search = UserBusSearch.objects.get(user=user)
            stops = user_search.search_stops.all().order_by('stop_order')
            serializer = UserBusSearchStopSerializer(stops, many=True)
            return Response({
                "stops": serializer.data
            }, status=status.HTTP_200_OK)
        except UserBusSearch.DoesNotExist:
            return Response({"stops": []}, status=status.HTTP_200_OK)
    

class BusBookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        return get_object_or_404(BusBooking, booking_id=pk, user=user)
    
    def get(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = SingleBusBookingSerializer(booking)
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


class UserBookingsByStatus(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, status_filter):
        user = request.user
        package_bookings = PackageBooking.objects.filter(trip_status=status_filter, user=user)
        bus_bookings = BusBooking.objects.filter(trip_status=status_filter, user=user)

        package_serializer = PackageFilterSerializer(package_bookings, many=True,context={'request': request})
        bus_serializer = BusFilterSerializer(bus_bookings, many=True,context={'request': request})

        for item in package_serializer.data:
            item['booking_type'] = 'package'
        
        for item in bus_serializer.data:
            item['booking_type'] = 'bus'

        combined_data = list(chain(package_serializer.data, bus_serializer.data))

        sorted_combined_data = sorted(combined_data, key=lambda x: x['created_at'], reverse=True)

        return Response(sorted_combined_data)
    
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

    def post(self, request):
        booking_id = request.data.get('booking_id')
        booking_type = request.data.get('booking_type')
        cancellation_reason = request.data.get('cancellation_reason')

        if not booking_id or not booking_type:
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
                return self._cancel_bus_booking(request, booking_id, cancellation_reason)

            elif booking_type == 'package':
                return self._cancel_package_booking(request, booking_id, cancellation_reason)

        except Exception as e:
            import traceback
            print("Traceback error:\n", traceback.format_exc())
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _cancel_bus_booking(self, request, booking_id, reason):
        try:
            booking = BusBooking.objects.get(booking_id=booking_id)

            if booking.user != request.user:
                return Response({"error": "You do not have permission to cancel this booking"},
                                status=status.HTTP_403_FORBIDDEN)

            if booking.payment_status == 'cancelled':
                return Response({"error": "This booking is already cancelled"},
                                status=status.HTTP_400_BAD_REQUEST)

            booking.payment_status = 'cancelled'
            booking.trip_status = 'cancelled'
            booking.cancellation_reason = reason 
            booking.save()

            send_notification(user=request.user,
                              message=f"Your bus booking with ID {booking_id} has been successfully canceled.")

            serializer = BusBookingSerializer(booking, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except BusBooking.DoesNotExist:
            return Response(
                {"error": f"Bus booking with id {booking_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

    def _cancel_package_booking(self, request, booking_id, reason):
        try:
            booking = PackageBooking.objects.get(booking_id=booking_id)

            if booking.user != request.user:
                return Response({"error": "You do not have permission to cancel this booking"},
                                status=status.HTTP_403_FORBIDDEN)

            if booking.payment_status == 'cancelled':
                return Response({"error": "This booking is already cancelled"},
                                status=status.HTTP_400_BAD_REQUEST)

            booking.payment_status = 'cancelled'
            booking.trip_status = 'cancelled'
            booking.cancellation_reason = reason 
            booking.save()

            send_notification(user=request.user,
                              message=f"Your package booking with ID {booking_id} has been successfully canceled.")

            serializer = PackageBookingSerializer(booking, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except PackageBooking.DoesNotExist:
            return Response(
                {"error": f"Package booking with id {booking_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        



class BookingFilterByDate(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # def get(self, request, booking_type, date):
    #     try:
    #         vendor = Vendor.objects.get(user=request.user)
    #     except Vendor.DoesNotExist:
    #         return Response(
    #             {"detail": "Unauthorized: Only vendors can access this data."},
    #             status=status.HTTP_403_FORBIDDEN
    #         )

    #     parsed_date = parse_date(date)
    #     if not parsed_date:
    #         return Response(
    #             {"error": "Invalid date format. Use YYYY-MM-DD."},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     start_datetime = datetime.combine(parsed_date, time.min)
    #     end_datetime = datetime.combine(parsed_date, time.max)

    #     if booking_type == 'bus':
    #         bookings = BusBooking.objects.filter(
    #             created_at__gte=start_datetime,
    #             created_at__lte=end_datetime,
    #             bus__vendor=vendor
    #         )


    #         serializer = BusBookingSerializer(bookings, many=True)
    #     elif booking_type == 'package':
    #         bookings = PackageBooking.objects.filter(
    #             created_at__gte=start_datetime,
    #             created_at__lte=end_datetime,
    #             package__vendor=vendor
    #         )
    #         serializer = PackageBookingSerializer(bookings, many=True)
    #     elif booking_type == 'all':
    #         bus_bookings = BusBooking.objects.filter(
    #             created_at__gte=start_datetime,
    #             created_at__lte=end_datetime,
    #             bus__vendor=vendor
    #         )
    #         package_bookings = PackageBooking.objects.filter(
    #             created_at__gte=start_datetime,
    #             created_at__lte=end_datetime,
    #             package__vendor=vendor
    #         )
            
    #         bus_data = BusBookingSerializer(bus_bookings, many=True).data
    #         package_data = PackageBookingSerializer(package_bookings, many=True).data
            
    #         return Response({
    #             "bus_bookings": bus_data,
    #             "package_bookings": package_data
    #         }, status=status.HTTP_200_OK)
    #     else:
    #         return Response(
    #             {"error": "Invalid booking type. Must be 'bus', 'package', or 'all'."},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     return Response(serializer.data, status=status.HTTP_200_OK)
    


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
                start_date__gte=start_datetime,
                start_date__lte=end_datetime,
                bus__vendor=vendor,
                trip_status="ongoing"
            )
            serializer = BusBookingSerializer(bookings, many=True, context={'request': request})

        elif booking_type == 'package':
            bookings = PackageBooking.objects.filter(
                start_date__gte=start_datetime,
                start_date__lte=end_datetime,
                package__vendor=vendor,
                trip_status="ongoing"
            )
            serializer = PackageBookingSerializer(bookings, many=True, context={'request': request})

        elif booking_type == 'all':
            bus_bookings = BusBooking.objects.filter(
                start_date__gte=start_datetime,
                start_date__lte=end_datetime,
                bus__vendor=vendor,
                trip_status="ongoing"
            )
            package_bookings = PackageBooking.objects.filter(
                start_date__gte=start_datetime,
                start_date__lte=end_datetime,
                package__vendor=vendor,
                trip_status="ongoing"
            )

            bus_data = BusBookingSerializer(bus_bookings, many=True, context={'request': request}).data
            package_data = PackageBookingSerializer(package_bookings, many=True, context={'request': request}).data

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

            











class PackageCategoryListAPIView(APIView):
    def get(self, request):
        search_query = request.query_params.get('search', '')
        
        if search_query:
            categories = PackageCategory.objects.filter(name__icontains=search_query)
        else:
            categories = PackageCategory.objects.all()

        serializer = PackageCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PackageSubCategoryListAPIView(APIView):
    def get(self, request,category):
        subcategories = PackageSubCategory.objects.filter(category=category)
        serializer = PackageSubCategorySerializer(subcategories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PopularBusApi(APIView):
    def get(self,request):
        buses = Bus.objects.filter(is_popular=True)
        serializer = PopularBusSerializer(buses,many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class PackageDriverDetailListAPIView(APIView):
    def get(self, request,booking_id):
        booking = PackageBooking.objects.get(booking_id=booking_id)
        drivers = PackageDriverDetail.objects.filter(package_booking=booking).first()
        serializer = PackageDriverDetailSerializer(drivers)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


class FooterSectionListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        footer_sections = FooterSection.objects.all()
        serializer = FooterSectionSerializer(footer_sections, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

# class AdvertisementListAPIView(APIView):
#     def get(self, request, *args, **kwargs):
#         advertisements = Advertisement.objects.all()
#         serializer = AdvertisementSerializer(advertisements, many=True, context={'request': request})



class AdvertisementListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        advertisements = Advertisement.objects.all()
        serializer = AdvertisementSerializer(
            advertisements,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class PackageDriverDetailListAPIView(APIView):
    def get(self, request, booking_id):
        try:
            booking = PackageBooking.objects.get(booking_id=booking_id)
        except PackageBooking.DoesNotExist:
            return Response(
                {"error": f"No booking found with booking_id '{booking_id}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        drivers = PackageDriverDetail.objects.filter(package_booking=booking).first()
        serializer = PackageDriverDetailSerializer(drivers)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class BusDriverDetailListAPIView(APIView):
    def get(self, request, booking_id):
        try:
            booking = BusBooking.objects.get(booking_id=booking_id)
        except BusBooking.DoesNotExist:
            return Response(
                {"error": f"No booking found with booking_id '{booking_id}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        drivers = BusDriverDetail.objects.filter(bus_booking=booking).first()
        serializer = BusDriverDetailSerializer(drivers)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserBusSearchCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user_search = UserBusSearch.objects.get(user=request.user)
            serializer = UserBusSearchSerializer(user_search, data=request.data)
        except UserBusSearch.DoesNotExist:
            serializer = UserBusSearchSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PilgrimagePackagesAPIView(APIView):
    def get(self, request, format=None):
        try:
            pilgrimage_category = PackageCategory.objects.get(name__iexact='pilgrimage')
        except PackageCategory.DoesNotExist:
            return Response({"detail": "Pilgrimage category not found."}, status=status.HTTP_404_NOT_FOUND)

        subcategories = PackageSubCategory.objects.filter(category=pilgrimage_category)
        serializer = PackageSubCategorySerializer(subcategories, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    




class BusBookingUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, booking_id):
        booking = get_object_or_404(BusBooking, booking_id=booking_id, user=request.user)
        
        # Use the dedicated update serializer
        serializer = BusBookingUpdateSerializer(
            booking,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            booking = serializer.save()
            
            bus_name = booking.bus.name if hasattr(booking.bus, 'name') else "Bus"
            route_info = f"from {booking.from_location} to {booking.to_location}" if booking.from_location and booking.to_location else ""
            
            send_notification(
                user=request.user,
                message=f"Your bus booking {bus_name} {route_info} has been successfully updated! Booking ID: {booking.booking_id}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)















from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from .models import BusBooking, PackageBooking, Vendor, AdminCommissionSlab, PayoutHistory, PayoutBooking
from vendors.models import VendorBankDetail
from .serializers import PayoutHistorySerializer
from bookings.models import WalletTransaction
from datetime import datetime
from operator import itemgetter
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
import logging
from users.models import Wallet
from admin_panel.models import AdminCommission, AdminCommissionSlab
from .services import WalletTransactionService

logger = logging.getLogger(__name__)

class UnpaidBookingsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_id = request.query_params.get('vendor_id')
        
        # Filter bus bookings
        bus_bookings = BusBooking.objects.filter(
            Q(payment_status__in=['partial', 'paid']) & Q(payout_status=False)
        )
        # Filter package bookings
        package_bookings = PackageBooking.objects.filter(
            Q(payment_status__in=['partial', 'paid']) & Q(payout_status=False)
        )

        # Filter by vendor_id if provided
        if vendor_id:
            bus_bookings = bus_bookings.filter(bus__vendor_id=vendor_id)
            package_bookings = package_bookings.filter(package__vendor_id=vendor_id)

        # Helper function to calculate admin commission
        def calculate_admin_commission(booking_amount):
            slab = AdminCommissionSlab.objects.filter(
                min_amount__lte=booking_amount,
                max_amount__gte=booking_amount
            ).first()
            
            if slab:
                return (booking_amount * slab.commission_percentage) / 100
            return 0

        # Helper function to get vendor bank details
        def get_vendor_ifsc(vendor):
            try:
                bank_detail = VendorBankDetail.objects.get(vendor=vendor)
                return bank_detail.ifsc_code
            except VendorBankDetail.DoesNotExist:
                return ''
            
        def get_vendor_account(vendor):
            try:
                bank_detail = VendorBankDetail.objects.get(vendor=vendor)
                return bank_detail.account_number
            except VendorBankDetail.DoesNotExist:
                return ''

        # Serialize bus bookings
        bus_data = []
        for b in bus_bookings:
            admin_commission = calculate_admin_commission(b.total_amount)
            bus_data.append({
                'booking_id': b.booking_id,
                'vendor_id': b.bus.vendor.user.id,
                'vendor_email': b.bus.vendor.email_address,
                'vendor_phone': b.bus.vendor.phone_no,
                'vendor_name': b.bus.vendor.full_name,
                'vendor_ifsc_code': get_vendor_ifsc(b.bus.vendor),
                'vendor_account_number':get_vendor_account(b.bus.vendor),
                'reward':0,
                'payout_mode':"account",
                'date': b.start_date,
                'amount': b.total_amount,
                'admin_commission': admin_commission,
                'net_amount': b.total_amount - admin_commission,
                'created_at': b.created_at,
                'type': 'bus'
            })

        # Serialize package bookings
        package_data = []
        for p in package_bookings:
            admin_commission = calculate_admin_commission(p.total_amount)
            package_data.append({
                'booking_id': p.booking_id,
                'vendor_id': p.package.vendor.user.id,
                'vendor_email': p.package.vendor.email_address,
                'vendor_phone': p.package.vendor.phone_no,
                'vendor_name': p.package.vendor.full_name,
                'vendor_ifsc_code': get_vendor_ifsc(p.package.vendor),
                'vendor_account_number':get_vendor_account(p.package.vendor),
                'reward':0,
                'payout_mode':"account",
                'date': p.start_date,
                'amount': p.total_amount,
                'admin_commission': admin_commission,
                'net_amount': p.total_amount - admin_commission,
                'created_at': p.created_at,
                'type': 'package'
            })

        # Combine and sort by created_at (newest first)
        combined_data = sorted(bus_data + package_data, key=itemgetter('created_at'), reverse=True)

        return Response(combined_data)

class CreatePayoutAPI(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        vendor_id = request.data.get('vendor_id')
        booking_ids = request.data.get('booking_ids', [])  # List of {'type': 'bus/package', 'id': x}
        payout_mode = request.data.get('payout_mode')
        payout_reference = request.data.get('payout_reference', '')
        note = request.data.get('note', '')
        
        try:
            vendor = Vendor.objects.get(user_id=vendor_id)
        except Vendor.DoesNotExist:
            return Response({'error': 'Vendor not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Validate bookings
        bus_bookings = []
        package_bookings = []
        total_amount = 0
        total_commission = 0
        
        for booking in booking_ids:
            try:
                if booking['type'] == 'bus':
                    b = BusBooking.objects.get(
                        booking_id=booking['id'],
                        payment_status__in=['partial', 'paid'],
                        payout_status=False,
                        bus__vendor=vendor
                    )
                    bus_bookings.append(b)
                elif booking['type'] == 'package':
                    p = PackageBooking.objects.get(
                        booking_id=booking['id'],
                        payment_status__in=['partial', 'paid'],
                        payout_status=False,
                        package__vendor=vendor
                    )
                    package_bookings.append(p)
            except (BusBooking.DoesNotExist, PackageBooking.DoesNotExist):
                return Response({'error': f"Booking {booking['id']} not found or already paid"}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate commissions and totals
        payout_bookings = []
        
        for booking in bus_bookings:
            # Find commission slab
            slab = AdminCommissionSlab.objects.filter(
                min_amount__lte=booking.total_amount,
                max_amount__gte=booking.total_amount
            ).first()
            
            if not slab:
                return Response({'error': f'No commission slab found for booking {booking.booking_id}'},
                              status=status.HTTP_400_BAD_REQUEST)
            
            commission = (booking.total_amount * slab.commission_percentage) / 100
            total_amount += booking.total_amount
            total_commission += commission
            
            payout_bookings.append({
                'type': 'bus',
                'booking': booking,
                'amount': booking.total_amount,
                'commission': commission
            })
        
        for booking in package_bookings:
            # Find commission slab
            slab = AdminCommissionSlab.objects.filter(
                min_amount__lte=booking.total_amount,
                max_amount__gte=booking.total_amount
            ).first()
            
            if not slab:
                return Response({'error': f'No commission slab found for booking {booking.booking_id}'},
                              status=status.HTTP_400_BAD_REQUEST)
            
            commission = (booking.total_amount * slab.commission_percentage) / 100
            total_amount += booking.total_amount
            total_commission += commission
            
            payout_bookings.append({
                'type': 'package',
                'booking': booking,
                'amount': booking.total_amount,
                'commission': commission
            })
        
        # Create payout record
        payout = PayoutHistory.objects.create(
            admin=request.user,
            vendor=vendor,
            payout_mode=payout_mode,
            payout_reference=payout_reference,
            total_amount=total_amount,
            admin_commission=total_commission,
            net_amount=total_amount - total_commission,
            note=note
        )
        
        # Create payout booking records and update bookings
        for pb in payout_bookings:
            PayoutBooking.objects.create(
                payout=payout,
                booking_type=pb['type'],
                booking_id=pb['booking'].booking_id,
                amount=pb['amount'],
                commission=pb['commission']
            )
            
            # Update booking
            pb['booking'].payout_status = True
            pb['booking'].payout = payout
            pb['booking'].save()
        
        # Get bank details
        bank_details = None
        try:
            bank_details = VendorBankDetail.objects.get(vendor=vendor)
        except VendorBankDetail.DoesNotExist:
            pass
        
        response_data = {
            'payout_id': payout.id,
            'vendor': vendor.full_name,
            'payout_date': payout.payout_date,
            'total_amount': total_amount,
            'admin_commission': total_commission,
            'net_amount': total_amount - total_commission,
            'bank_details': {
                'account_number': bank_details.account_number if bank_details else '',
                'ifsc_code': bank_details.ifsc_code if bank_details else '',
                'holder_name': bank_details.holder_name if bank_details else ''
            } if bank_details else None
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)

class PayoutHistoryAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        vendor_id = request.query_params.get('vendor_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        payouts = PayoutHistory.objects.all().order_by('-payout_date')
        
        if vendor_id:
            payouts = payouts.filter(vendor_id=vendor_id)
        
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                payouts = payouts.filter(payout_date__date__range=[start_date, end_date])
            except ValueError:
                pass
        
        serializer = PayoutHistorySerializer(payouts, many=True)
        return Response(serializer.data)

class PayoutDetailAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, payout_id):
        try:
            payout = PayoutHistory.objects.get(id=payout_id)
            serializer = PayoutHistorySerializer(payout)
            return Response(serializer.data)
        except PayoutHistory.DoesNotExist:
            return Response({'error': 'Payout not found'}, status=status.HTTP_404_NOT_FOUND)

# Helper function to get admin commission from database
def get_admin_commission_from_db(amount):
    """Get admin commission percentage and revenue from database"""
    try:
        slab = AdminCommissionSlab.objects.filter(
            min_amount__lte=amount,
            max_amount__gte=amount
        ).first()
        
        if slab:
            commission_percent = slab.commission_percentage
            revenue = (amount * commission_percent) / 100
            return commission_percent, revenue
        return 0, 0
    except Exception as e:
        logger.error(f"Error getting admin commission: {str(e)}")
        return 0, 0













logger = logging.getLogger(__name__)

class ApplyWalletToBusBookingAPIView(APIView):
    """Apply wallet balance to bus booking"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            # Get the booking
            booking = get_object_or_404(BusBooking, booking_id=booking_id, user=request.user)
            
            # Check if wallet has already been applied
            if WalletTransactionService.has_wallet_been_applied(booking_id, 'bus', request.user):
                return Response({
                    "error": "Wallet balance has already been applied to this booking"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user's wallet
            try:
                wallet = Wallet.objects.get(user=request.user)
            except Wallet.DoesNotExist:
                return Response({
                    "error": "Wallet not found for user"
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if wallet balance is available
            if wallet.balance <= 0:
                return Response({
                    "error": "No wallet balance available"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Use the minimum of wallet balance or booking total amount
            # This allows partial wallet usage if wallet balance is less than total amount
            wallet_amount_to_use = min(wallet.balance, booking.total_amount)
            
            # Apply wallet using service
            wallet_transaction, updated_wallet = WalletTransactionService.apply_wallet_to_booking(
                user=request.user,
                booking_id=booking_id,
                booking_type='bus',
                wallet_amount=wallet_amount_to_use,
                description=f"Applied ₹{wallet_amount_to_use} to bus booking {booking_id}"
            )
            
            # Update booking total amount
            new_total_amount = booking.total_amount - wallet_amount_to_use
            booking.total_amount = new_total_amount
            booking.save()

            # Update admin commission
            commission_percent, revenue = get_admin_commission_from_db(new_total_amount)
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='bus', 
                    booking_id=booking.booking_id
                )
                admin_commission.revenue_to_admin = revenue
                admin_commission.commission_percentage = commission_percent
                admin_commission.save()
                logger.info(f"Updated admin commission for bus booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                logger.warning(f"Admin commission not found for booking {booking.booking_id}")

            return Response({
                "message": "Wallet balance applied successfully",
                "wallet_amount_used": float(wallet_amount_to_use),
                "new_total_amount": float(new_total_amount),
                "remaining_wallet_balance": float(updated_wallet.balance),
                "transaction_id": wallet_transaction.id,
                "wallet_used": True
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error applying wallet to bus booking: {str(e)}")
            return Response({
                "error": f"Error applying wallet balance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RemoveWalletFromBusBookingAPIView(APIView):
    """Remove wallet balance from bus booking"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            # Get the booking
            booking = get_object_or_404(BusBooking, booking_id=booking_id, user=request.user)
            
            # Remove wallet using service (updates existing transaction instead of creating new one)
            updated_transaction, updated_wallet, wallet_amount_restored = WalletTransactionService.remove_wallet_from_booking(
                user=request.user,
                booking_id=booking_id,
                booking_type='bus',
                description=f"Removed from bus booking {booking_id}"
            )
            
            # Restore the original total amount
            original_total_amount = booking.total_amount + wallet_amount_restored
            booking.total_amount = original_total_amount
            booking.save()

            # Update admin commission
            commission_percent, revenue = get_admin_commission_from_db(original_total_amount)
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='bus', 
                    booking_id=booking.booking_id
                )
                admin_commission.revenue_to_admin = revenue
                admin_commission.commission_percentage = commission_percent
                admin_commission.save()
                logger.info(f"Updated admin commission for bus booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                logger.warning(f"Admin commission not found for booking {booking.booking_id}")

            return Response({
                "message": "Wallet balance removed successfully",
                "wallet_amount_restored": float(wallet_amount_restored),
                "new_total_amount": float(original_total_amount),
                "current_wallet_balance": float(updated_wallet.balance),
                "transaction_id": updated_transaction.id,
                "wallet_used": False
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error removing wallet from bus booking: {str(e)}")
            return Response({
                "error": f"Error removing wallet balance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplyWalletToPackageBookingAPIView(APIView):
    """Apply wallet balance to package booking"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            # Get the booking
            booking = get_object_or_404(PackageBooking, booking_id=booking_id, user=request.user)
            
            # Check if wallet has already been applied
            if WalletTransactionService.has_wallet_been_applied(booking_id, 'package', request.user):
                return Response({
                    "error": "Wallet balance has already been applied to this booking"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user's wallet
            try:
                wallet = Wallet.objects.get(user=request.user)
            except Wallet.DoesNotExist:
                return Response({
                    "error": "Wallet not found for user"
                }, status=status.HTTP_404_NOT_FOUND)

            # Check wallet balance
            if wallet.balance <= 0:
                return Response({
                    "error": "No wallet balance available"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Use the minimum of wallet balance or booking total amount
            # This allows partial wallet usage if wallet balance is less than total amount
            wallet_amount_to_use = min(wallet.balance, booking.total_amount)
            
            # Apply wallet using service
            wallet_transaction, updated_wallet = WalletTransactionService.apply_wallet_to_booking(
                user=request.user,
                booking_id=booking_id,
                booking_type='package',
                wallet_amount=wallet_amount_to_use,
                description=f"Applied ₹{wallet_amount_to_use} to package booking {booking_id}"
            )
            
            # Update booking total amount
            new_total_amount = booking.total_amount - wallet_amount_to_use
            booking.total_amount = new_total_amount
            booking.save()

            # Update admin commission
            commission_percent, revenue = get_admin_commission_from_db(new_total_amount)
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='package', 
                    booking_id=booking.booking_id
                )
                admin_commission.revenue_to_admin = revenue
                admin_commission.commission_percentage = commission_percent
                admin_commission.save()
                logger.info(f"Updated admin commission for package booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                logger.warning(f"Admin commission not found for booking {booking.booking_id}")

            return Response({
                "message": "Wallet balance applied successfully",
                "wallet_amount_used": float(wallet_amount_to_use),
                "new_total_amount": float(new_total_amount),
                "remaining_wallet_balance": float(updated_wallet.balance),
                "transaction_id": wallet_transaction.id,
                "wallet_used": True
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error applying wallet to package booking: {str(e)}")
            return Response({
                "error": f"Error applying wallet balance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RemoveWalletFromPackageBookingAPIView(APIView):
    """Remove wallet balance from package booking"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            # Get the booking
            booking = get_object_or_404(PackageBooking, booking_id=booking_id, user=request.user)
            
            # Remove wallet using service (updates existing transaction instead of creating new one)
            updated_transaction, updated_wallet, wallet_amount_restored = WalletTransactionService.remove_wallet_from_booking(
                user=request.user,
                booking_id=booking_id,
                booking_type='package',
                description=f"Removed from package booking {booking_id}"
            )
            
            # Restore the original total amount
            original_total_amount = booking.total_amount + wallet_amount_restored
            booking.total_amount = original_total_amount
            booking.save()

            # Update admin commission
            commission_percent, revenue = get_admin_commission_from_db(original_total_amount)
            try:
                admin_commission = AdminCommission.objects.get(
                    booking_type='package', 
                    booking_id=booking.booking_id
                )
                admin_commission.revenue_to_admin = revenue
                admin_commission.commission_percentage = commission_percent
                admin_commission.save()
                logger.info(f"Updated admin commission for package booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                logger.warning(f"Admin commission not found for booking {booking.booking_id}")

            return Response({
                "message": "Wallet balance removed successfully",
                "wallet_amount_restored": float(wallet_amount_restored),
                "new_total_amount": float(original_total_amount),
                "current_wallet_balance": float(updated_wallet.balance),
                "transaction_id": updated_transaction.id,
                "wallet_used": False
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error removing wallet from package booking: {str(e)}")
            return Response({
                "error": f"Error removing wallet balance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetWalletBalanceAPIView(APIView):
    """Get user's current wallet balance and recent transactions"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)

            wallet_used = wallet.wallet_used

            recent_transactions = WalletTransactionService.get_user_wallet_transactions(
                user=request.user, 
                limit=10
            )

            transactions_data = [{
                "id": txn.id,
                "booking_id": txn.booking_id,
                "booking_type": txn.booking_type,
                "transaction_type": txn.transaction_type,
                "amount": float(txn.amount),
                "balance_before": float(txn.balance_before),
                "balance_after": float(txn.balance_after),
                "description": txn.description,
                "created_at": txn.created_at.isoformat(),
                "is_active": txn.is_active
            } for txn in recent_transactions]

            return Response({
                "balance": float(wallet.balance),
                "wallet_used": wallet_used,
                "recent_transactions": transactions_data
            }, status=status.HTTP_200_OK)

        except Wallet.DoesNotExist:
            return Response({
                "balance": 0.00,
                "wallet_used": False,
                "recent_transactions": [],
                "message": "Wallet not found"
            }, status=status.HTTP_200_OK)


class WalletTransactionHistoryAPIView(APIView):
    """Get detailed wallet transaction history"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            transaction_type = request.GET.get('transaction_type', None)
            booking_type = request.GET.get('booking_type', None)
            
            # Build query - show all transactions regardless of is_active status
            queryset = WalletTransaction.objects.filter(user=request.user).order_by('-created_at')
            
            if transaction_type:
                queryset = queryset.filter(transaction_type=transaction_type)
            
            if booking_type:
                queryset = queryset.filter(booking_type=booking_type)
            
            # Pagination
            offset = (page - 1) * limit
            transactions = queryset[offset:offset + limit]
            total_count = queryset.count()
            
            transactions_data = []
            for txn in transactions:
                transactions_data.append({
                    "id": txn.id,
                    "booking_id": txn.booking_id,
                    "booking_type": txn.booking_type,
                    "transaction_type": txn.transaction_type,
                    "amount": float(txn.amount),
                    "balance_before": float(txn.balance_before),
                    "balance_after": float(txn.balance_after),
                    "description": txn.description,
                    "created_at": txn.created_at.isoformat(),
                    "is_active": txn.is_active,
                    "reference_id": txn.reference_id
                })
            
            return Response({
                "transactions": transactions_data,
                "pagination": {
                    "current_page": page,
                    "total_pages": (total_count + limit - 1) // limit,
                    "total_count": total_count,
                    "has_next": offset + limit < total_count,
                    "has_previous": page > 1
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching wallet transaction history: {str(e)}")
            return Response({
                "error": "Error fetching transaction history"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        





class CompleteTripAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TripStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    booking = serializer.validated_data['booking']
                    
                    # Update trip status to completed
                    booking.trip_status = 'completed'
                    booking.save(update_fields=['trip_status'])
                    
                    # Prepare response data
                    response_data = {
                        'success': True,
                        'message': 'Trip status updated to completed successfully',
                        'booking_details': {
                            'booking_id': booking.booking_id,
                            'booking_type': serializer.validated_data['booking_type'],
                            'trip_status': booking.get_trip_status_display(),
                            'payment_status': booking.get_payment_status_display(),
                            'booking_status': booking.get_booking_status_display(),
                            'user': booking.user.username if booking.user else None,
                            'total_amount': str(booking.total_amount),
                            'start_date': booking.start_date,
                        }
                    }
                    
                    return Response(response_data, status=status.HTTP_200_OK)
                    
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'An error occurred while updating trip status: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    




class NearbyBusLocationAPIView(APIView):
    """
    Simple API to get buses near a location using lat/lon coordinates
    Usage: GET /api/buses/location/?lat=17.385044&lon=78.486671&radius=30
    """
    
    def get(self, request):
        # Get coordinates from query parameters
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        radius = request.query_params.get('radius', 50)  # Default 30km radius
        
        # Validate required parameters
        if not lat or not lon:
            return Response({
                "error": "Both 'lat' and 'lon' parameters are required",
                "example": "/api/buses/location/?lat=17.385044&lon=78.486671&radius=30"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            lat = float(lat)
            lon = float(lon)
            radius = float(radius)
        except ValueError:
            return Response({
                "error": "Invalid coordinates. Please provide valid numbers for lat, lon, and radius"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # User coordinates
        user_coords = (lat, lon)
        
        # Get all buses with valid coordinates
        buses = Bus.objects.filter(
            latitude__isnull=False, 
            longitude__isnull=False,
            status='available'  # Only available buses
        ).prefetch_related('amenities', 'features', 'bus_reviews', 'images')
        
        # Find nearby buses
        nearby_buses = []
        for bus in buses:
            if bus.latitude is not None and bus.longitude is not None:
                bus_coords = (bus.latitude, bus.longitude)
                distance_km = geodesic(user_coords, bus_coords).kilometers
                
                if distance_km <= radius:
                    nearby_buses.append({
                        'bus': bus,
                        'distance_km': round(distance_km, 2)
                    })
        
        if not nearby_buses:
            return Response({
                "message": f"No buses found within {radius} km of your location",
                "searched_location": {"lat": lat, "lon": lon, "radius": radius},
                "total_buses": 0,
                "buses": []
            }, status=status.HTTP_200_OK)
        
        # Sort by distance (nearest first)
        nearby_buses.sort(key=lambda x: x['distance_km'])
        
        # Serialize bus data
        buses_data = []
        for item in nearby_buses:
            bus = item['bus']
            
            # Get bus images
            bus_images = []
            for image in bus.images.all():
                bus_images.append({
                    'id': image.id,
                    'image': request.build_absolute_uri(image.image.url) if image.image else None,
                    'alt_text': getattr(image, 'alt_text', ''),
                    'is_primary': getattr(image, 'is_primary', False)
                })
            
            # Get amenities
            amenities = [
                {
                    'id': amenity.id,
                    'name': amenity.name,
                    'icon': request.build_absolute_uri(amenity.icon.url) if hasattr(amenity, 'icon') and amenity.icon else None
                }
                for amenity in bus.amenities.all()
            ]
            
            # Get features
            features = [
                {
                    'id': feature.id,
                    'name': feature.name
                }
                for feature in bus.features.all()
            ]
            
            bus_data = {
                'id': bus.id,
                'bus_name': bus.bus_name,
                'bus_number': bus.bus_number,
                'capacity': bus.capacity,
                'bus_type': bus.bus_type,
                'location': bus.location,
                'latitude': bus.latitude,
                'longitude': bus.longitude,
                'distance_km': item['distance_km'],
                'status': bus.status,
                'is_popular': bus.is_popular,
                'average_rating': bus.average_rating,
                'total_reviews': bus.total_reviews,
                'base_price': str(bus.base_price) if bus.base_price else None,
                'price_per_km': str(bus.price_per_km) if bus.price_per_km else None,
                'minimum_fare': str(bus.minimum_fare) if bus.minimum_fare else None,
                'night_allowance': str(bus.night_allowance) if bus.night_allowance else None,
                'travels_logo': request.build_absolute_uri(bus.travels_logo.url) if bus.travels_logo else None,
                'images': bus_images,
                'amenities': amenities,
                'features': features
            }
            
            buses_data.append(bus_data)
        
        response_data = {
            "message": f"Found {len(nearby_buses)} buses within {radius} km",
            "searched_location": {
                "lat": lat,
                "lon": lon,
                "radius": radius
            },
            "total_buses": len(nearby_buses),
            "buses": buses_data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    


# razooor pay


razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class CreatePaymentOrderAPIView(APIView):
    """Create Razorpay order for payment"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False, 
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking_id = serializer.validated_data['booking_id']
            booking_type = serializer.validated_data['booking_type']
            amount = serializer.validated_data['amount']
            
            # Get booking based on type
            if booking_type == 'bus':
                booking = get_object_or_404(BusBooking, booking_id=booking_id, user=request.user)
                booking_serializer = BusBookingSerializer(booking, context={'request': request})
            else:
                booking = get_object_or_404(PackageBooking, booking_id=booking_id, user=request.user)
                booking_serializer = PackageBookingSerializer(booking, context={'request': request})
            
            # Validate amount
            if amount <= 0 or amount > booking.balance_amount:
                return Response({
                    'success': False,
                    'error': f'Invalid amount. Maximum payable amount is {booking.balance_amount}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create Razorpay order
            order_data = {
                'amount': int(amount * 100),  # Amount in paisa
                'currency': 'INR',
                'receipt': f'booking_{booking_id}_{booking_type}',
                'notes': {
                    'booking_id': str(booking_id),
                    'booking_type': booking_type,
                    'user_id': str(request.user.id)
                }
            }
            
            order = razorpay_client.order.create(data=order_data)
            
            # Create payment transaction record
            if booking_type == 'bus':
                transaction = PaymentTransaction.objects.create(
                    booking=booking,
                    user=request.user,
                    amount=amount,
                    razorpay_order_id=order['id']
                )
            else:
                transaction = PaymentTransaction.objects.create(
                    package_booking=booking,
                    user=request.user,
                    amount=amount,
                    razorpay_order_id=order['id']
                )
            
            return Response({
                'success': True,
                'order_id': order['id'],
                'amount': float(amount),
                'currency': 'INR',
                'key': settings.RAZORPAY_KEY_ID,
                'booking': booking_serializer.data,
                'razorpay_order': {
                    'id': order['id'],
                    'amount': order['amount'],
                    'currency': order['currency'],
                    'receipt': order['receipt']
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False, 
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyPaymentAPIView(APIView):
    """Verify Razorpay payment signature"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentVerificationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            razorpay_order_id = serializer.validated_data['razorpay_order_id']
            razorpay_payment_id = serializer.validated_data['razorpay_payment_id']
            razorpay_signature = serializer.validated_data['razorpay_signature']
            
            # Verify signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params_dict)
                signature_verified = True
            except Exception as e:
                print(f"Signature verification failed: {e}")  # Add logging for debugging
                signature_verified = False
            
            # Get transaction first
            transaction = get_object_or_404(
                PaymentTransaction, 
                razorpay_order_id=razorpay_order_id,
                user=request.user
            )
            
            if signature_verified:
                # Update transaction
                transaction.razorpay_payment_id = razorpay_payment_id
                transaction.razorpay_signature = razorpay_signature
                transaction.status = 'success'
                transaction.save()
                
                # Update booking payment - Fixed logic
                booking = None
                booking_serializer_class = None
                
                if transaction.booking:
                    booking = transaction.booking
                    booking_serializer_class = BusBookingSerializer
                elif transaction.package_booking:
                    booking = transaction.package_booking
                    booking_serializer_class = PackageBookingSerializer
                else:
                    return Response({
                        'success': False,
                        'error': 'No booking associated with this transaction'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update booking details
                booking.paid_amount += transaction.amount
                booking.razorpay_order_id = razorpay_order_id
                booking.razorpay_payment_id = razorpay_payment_id
                booking.razorpay_signature = razorpay_signature
                booking.save()  # This will auto-update payment_status
                
                booking_serializer = booking_serializer_class(booking, context={'request': request})
                
                return Response({
                    'success': True,
                    'message': 'Payment verified successfully',
                    'transaction_id': transaction.id,
                    'booking': booking_serializer.data
                }, status=status.HTTP_200_OK)
            else:
                # Mark transaction as failed
                transaction.status = 'failed'
                transaction.save()
                
                return Response({
                    'success': False,
                    'error': 'Payment verification failed'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except PaymentTransaction.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in payment verification: {e}")
            return Response({
                'success': False, 
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BookingPaymentStatusAPIView(APIView):
    """Get booking payment status and details"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, booking_type, booking_id):
        try:
            if booking_type == 'bus':
                booking = get_object_or_404(BusBooking, booking_id=booking_id, user=request.user)
                serializer = BusBookingSerializer(booking, context={'request': request})
            elif booking_type == 'package':
                booking = get_object_or_404(PackageBooking, booking_id=booking_id, user=request.user)
                serializer = PackageBookingSerializer(booking, context={'request': request})
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid booking type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get payment transactions
            if booking_type == 'bus':
                transactions = PaymentTransaction.objects.filter(
                    booking=booking, 
                    user=request.user
                ).order_by('-created_at')
            else:
                transactions = PaymentTransaction.objects.filter(
                    package_booking=booking, 
                    user=request.user
                ).order_by('-created_at')
            
            transaction_data = []
            for txn in transactions:
                transaction_data.append({
                    'id': txn.id,
                    'amount': float(txn.amount),
                    'status': txn.status,
                    'razorpay_order_id': txn.razorpay_order_id,
                    'razorpay_payment_id': txn.razorpay_payment_id,
                    'created_at': txn.created_at,
                    'updated_at': txn.updated_at
                })
            
            return Response({
                'success': True,
                'booking': serializer.data,
                'transactions': transaction_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)