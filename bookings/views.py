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



class PackageListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, category):
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        total_travellers = request.query_params.get('total_travellers')

        if lat is None or lon is None:
            return Response(
                {"error": "Latitude (lat) and Longitude (lon) query parameters are required."},
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

        # Validate total_travellers if provided
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

        packages = Package.objects.filter(sub_category=category)
        if not packages.exists():
            return Response({"error": f"No packages found under category '{category}'."}, status=404)

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

        if not nearby_packages:
            message = f"No packages found near your location within 30 km"
            if travellers_count:
                message += f" with suitable capacity for {travellers_count} travellers"
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


class BusListAPIView(APIView):
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

        # If search has value, filter by name only (no location filtering)
        if search:
            buses = buses.filter(bus_name__icontains=search)
            buses_only = list(buses.distinct())
        else:
            # No search - apply location-based filtering (within 30 km)
            nearby_buses = []
            for bus in buses.distinct():
                if bus.latitude is not None and bus.longitude is not None:
                    bus_coords = (bus.latitude, bus.longitude)
                    distance_km = geodesic(user_coords, bus_coords).kilometers
                    if distance_km <= 30:
                        nearby_buses.append((bus, distance_km))

            if not nearby_buses:
                return Response({"message": "No buses found near your location within 30 km."}, status=200)

            buses_only = [bus for bus, dist in nearby_buses]

        if not buses_only:
            return Response({"message": "No buses found matching your criteria."}, status=200)

        # Get sorting parameter
        sort_by = request.query_params.get('sort_by', 'nearest')

        # Apply sorting
        if search:
            # For name-based search, no distance sorting
            if sort_by == 'popular':
                buses_only = [bus for bus in buses_only if getattr(bus, 'is_popular', False)]
            elif sort_by == 'top_rated':
                buses_only.sort(key=lambda x: x.bus_reviews.aggregate(avg=Avg('rating'))['avg'] or 0, reverse=True)
            elif sort_by == 'price_low_to_high':
                bus_prices = []
                for bus in buses_only:
                    price = self.calculate_trip_price(bus, user_search.from_lat, user_search.from_lon, 
                                                    user_search.to_lat, user_search.to_lon, user_search.seat or 1)
                    bus_prices.append((bus, price))
                bus_prices.sort(key=lambda x: x[1])
                buses_only = [bus for bus, price in bus_prices]
            elif sort_by == 'price_high_to_low':
                bus_prices = []
                for bus in buses_only:
                    price = self.calculate_trip_price(bus, user_search.from_lat, user_search.from_lon, 
                                                    user_search.to_lat, user_search.to_lon, user_search.seat or 1)
                    bus_prices.append((bus, price))
                bus_prices.sort(key=lambda x: x[1], reverse=True)
                buses_only = [bus for bus, price in bus_prices]
        else:
            # For location-based search, keep original sorting logic
            if sort_by == 'nearest':
                nearby_buses.sort(key=lambda x: x[1])  # Sort by distance
            elif sort_by == 'popular':
                nearby_buses = [(bus, dist) for bus, dist in nearby_buses if getattr(bus, 'is_popular', False)]
                nearby_buses.sort(key=lambda x: x[1])  # Then by distance
            elif sort_by == 'top_rated':
                nearby_buses.sort(key=lambda x: x[0].bus_reviews.aggregate(avg=Avg('rating'))['avg'] or 0, reverse=True)
            elif sort_by == 'price_low_to_high':
                bus_prices = []
                for bus, dist in nearby_buses:
                    price = self.calculate_trip_price(bus, user_search.from_lat, user_search.from_lon, 
                                                    user_search.to_lat, user_search.to_lon, user_search.seat or 1)
                    bus_prices.append((bus, dist, price))
                bus_prices.sort(key=lambda x: x[2])
                nearby_buses = [(bus, dist) for bus, dist, price in bus_prices]
            elif sort_by == 'price_high_to_low':
                bus_prices = []
                for bus, dist in nearby_buses:
                    price = self.calculate_trip_price(bus, user_search.from_lat, user_search.from_lon, 
                                                    user_search.to_lat, user_search.to_lon, user_search.seat or 1)
                    bus_prices.append((bus, dist, price))
                bus_prices.sort(key=lambda x: x[2], reverse=True)
                nearby_buses = [(bus, dist) for bus, dist, price in bus_prices]
            
            buses_only = [bus for bus, dist in nearby_buses]

        response_data = {
            'buses': buses_only
        }

        serializer = BusListResponseSerializer(
            response_data, 
            context={'request': request, 'user_search': user_search}
        )
        return Response(serializer.data)


    def calculate_distance_google_api(self, from_lat, from_lon, to_lat, to_lon):
        """
        Calculate distance using Google Distance Matrix API
        Returns distance in kilometers
        """
        try:
            import requests
            from django.conf import settings
            from decimal import Decimal
            import logging
            
            # Google Distance Matrix API endpoint
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            
            # API parameters
            params = {
                'origins': f"{from_lat},{from_lon}",
                'destinations': f"{to_lat},{to_lon}",
                'units': 'metric',
                'mode': 'driving',
                'key': settings.GOOGLE_DISTANCE_MATRIX_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] == 'OK':
                element = data['rows'][0]['elements'][0]
                if element['status'] == 'OK':
                    # Distance in meters, convert to kilometers
                    distance_km = element['distance']['value'] / 1000
                    return Decimal(str(round(distance_km, 2)))
                else:
                    raise Exception(f"Google API element error: {element['status']}")
            else:
                raise Exception(f"Google API error: {data['status']}")
                
        except Exception as e:
            logging.error(f"Error calculating distance with Google API: {str(e)}")
            # Fallback to simple calculation if API fails
            return self.calculate_distance_fallback(from_lat, from_lon, to_lat, to_lon)

    def calculate_distance_fallback(self, from_lat, from_lon, to_lat, to_lon):
        """
        Fallback distance calculation using Haversine formula
        Returns distance in kilometers
        """
        try:
            from math import radians, cos, sin, asin, sqrt
            from decimal import Decimal
            import logging
            
            # Convert decimal degrees to radians
            from_lat, from_lon, to_lat, to_lon = map(radians, [from_lat, from_lon, to_lat, to_lon])
            
            # Haversine formula
            dlat = to_lat - from_lat
            dlon = to_lon - from_lon
            a = sin(dlat/2)**2 + cos(from_lat) * cos(to_lat) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of earth in kilometers
            
            distance_km = c * r
            return Decimal(str(round(distance_km, 2)))
        except Exception as e:
            logging.error(f"Error in fallback distance calculation: {str(e)}")
            return Decimal('10.0')  # Default fallback distance

    def calculate_trip_price(self, bus, from_lat, from_lon, to_lat, to_lon, seat_count):
        """
        Calculate trip price based on distance and bus pricing
        """
        try:
            from decimal import Decimal
            
            # Calculate distance
            distance_km = self.calculate_distance_google_api(from_lat, from_lon, to_lat, to_lon)
            
            base_price = bus.base_price or Decimal('0.00')
            base_price_km = bus.base_price_km or 0
            price_per_km = bus.price_per_km or Decimal('0.00')
            minimum_fare = bus.minimum_fare or Decimal('0.00')
            
            # Calculate amount based on distance
            if distance_km <= base_price_km:
                # Within base price range
                total_amount = base_price
            else:
                # Base price + additional km charges
                additional_km = distance_km - base_price_km
                additional_charges = additional_km * price_per_km
                total_amount = base_price + additional_charges
            
            # Apply seat multiplier
            total_amount = total_amount * seat_count
            
            # Ensure minimum fare is met
            if total_amount < minimum_fare:
                total_amount = minimum_fare
            
            return total_amount
            
        except Exception as e:
            return Decimal('0.00')
    



class SingleBusListAPIView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request,bus_id):
        buses = Bus.objects.get(id=bus_id)
        serializer = BusListingSerializer(buses, many=False, context={'request': request})
        return Response(serializer.data)

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
            vendor = package.vendor
            booking_date = serializer.validated_data['start_date']

            if is_vendor_busy(vendor, booking_date):
                return Response({"error": "Vendor is busy on the selected date."}, status=status.HTTP_400_BAD_REQUEST)

            booking = serializer.save(user=request.user)


            package_name = booking.package.name if hasattr(booking.package, 'name') else "Tour package"
            send_notification(
                user=request.user,
                message=f"Your booking for {package_name} has been successfully created! Booking ID: {booking.booking_id}"
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
                end_date = user_search.return_date if not user_search.one_way else start_date
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
                
                send_notification(
                    user=user,
                    message=f"Your bus booking for {bus_name} {route_info} has been confirmed! "
                           f"Booking ID: {booking.booking_id}"
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creating bus booking: {str(e)}")
                return Response(
                    {"error": "An error occurred while creating the booking. Please try again."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

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
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                bus__vendor=vendor
            )
            serializer = BusBookingSerializer(bookings, many=True, context={'request': request})

        elif booking_type == 'package':
            bookings = PackageBooking.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                package__vendor=vendor
            )
            serializer = PackageBookingSerializer(bookings, many=True, context={'request': request})

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