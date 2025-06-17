
from rest_framework import serializers
from .models import BusBooking, PackageBooking, Travelers, UserBusSearch, PackageDriverDetail,PayoutHistory,BusDriverDetail
from vendors.models import Package, Bus
from admin_panel.utils import get_admin_commission_from_db, get_advance_amount_from_db
from admin_panel.models import AdminCommission
from django.contrib.auth import get_user_model
from users.models import Wallet, ReferralRewardTransaction
from decimal import Decimal
from vendors.models import Package, PackageImage, DayPlan, Place, PlaceImage, Stay, StayImage, Meal, MealImage, Activity, ActivityImage
from django.db import models
from users.models import Favourite
from django.db.models import Avg
from vendors.models import *
from datetime import timedelta
from django.conf import settings
import requests
from geopy.distance import geodesic
import logging
from django.db import transaction
import math
logger = logging.getLogger(__name__)
from reviews.serializers import *
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from notifications.utils import send_notification
from .models import BusBookingStop,UserBusSearchStop


User = get_user_model()

# Minimum wallet amount required for using wallet balance
MINIMUM_WALLET_AMOUNT = Decimal('1000.00')


class BusBookingStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusBookingStop
        fields = ['id', 'stop_order', 'location_name', 'latitude', 'longitude', 
                 'estimated_arrival', 'distance_from_previous']
        read_only_fields = ['id', 'distance_from_previous', 'estimated_arrival']


class UserBusSearchStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBusSearchStop
        fields = ['id', 'stop_order', 'location_name', 'latitude', 'longitude']
        read_only_fields = ['id']

class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'age', 
                 'dob', 'id_proof', 'email', 'mobile', 'city', 'place', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'bus_booking': {'read_only': True},
            'package_booking': {'read_only': True},
            'created_at': {'read_only': True}
        }

class BaseBookingSerializer(serializers.ModelSerializer):
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        abstract = True
        fields = ['booking_id', 'user', 'start_date','total_amount', 'advance_amount', 
                 'payment_status', 'booking_status', 'trip_status', 'created_at', 
                 'balance_amount', 'cancellation_reason', 'total_travelers', 
                 'male', 'female', 'children', 'from_location', 'to_location']
        read_only_fields = ['id', 'created_at', 'balance_amount']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
            'start_date': {'required': False},
        }

import requests
import logging
from decimal import Decimal
from django.conf import settings

class BusBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    end_date = serializers.DateField(required=False, help_text="End date of the trip")
    stops = BusBookingStopSerializer(many=True, read_only=True)
    
    # Stops data for creating booking with stops
    stops_data = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        help_text="List of stops with location_name, latitude, longitude"
    )

    # Partial payment field
    partial_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        write_only=True,
        help_text="Amount user chooses to pay initially. Must be >= advance_amount."
    )

    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'travelers', 'booking_type', 
            'partial_amount', 'return_date', 'pick_up_time', 'price', 'end_date',
            'night_allowance_total', 'base_price_days', 'total_distance', 'stops', 'stops_data'
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
            'total_amount': {'write_only': False, 'required': False},
            'total_travelers': {'read_only': True},
            'total_distance': {'read_only': True}
        }

    def validate_stops_data(self, value):
        """Validate stops data"""
        if not value:
            return value
            
        for i, stop in enumerate(value):
            if not all(key in stop for key in ['location_name', 'latitude', 'longitude']):
                raise serializers.ValidationError(
                    f"Stop {i+1} must have location_name, latitude, and longitude"
                )
            
            try:
                float(stop['latitude'])
                float(stop['longitude'])
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Stop {i+1} has invalid latitude or longitude"
                )
        
        return value

    def validate(self, data):
        user = self.context['request'].user

        try:
            bus_search = UserBusSearch.objects.get(user=user)
            if not data.get('start_date') and bus_search.pick_up_date:
                data['start_date'] = bus_search.pick_up_date
        except UserBusSearch.DoesNotExist:
            pass

        # Validate dates
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        return_date = data.get('return_date')

        if not start_date:
            raise serializers.ValidationError("Start date is required. Please search for buses first.")
        
        if start_date < timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the past.")

        # Set end_date - if return_date is provided, use it; otherwise use start_date for same-day trips
        if return_date:
            if return_date < start_date:
                raise serializers.ValidationError("Return date cannot be before start date.")
            data['end_date'] = return_date
        elif not end_date:
            data['end_date'] = start_date

        return data

    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data
    
    def get_booking_type(self, obj):
        return "bus"

    def calculate_distance_google_api(self, from_lat, from_lon, to_lat, to_lon):
        """Calculate distance using Google Distance Matrix API"""
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
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
                    distance_km = element['distance']['value'] / 1000
                    return Decimal(str(round(distance_km, 2)))
                else:
                    raise Exception(f"Google API element error: {element['status']}")
            else:
                raise Exception(f"Google API error: {data['status']}")
                
        except Exception as e:
            logging.error(f"Error calculating distance with Google API: {str(e)}")
            return self.calculate_distance_fallback(from_lat, from_lon, to_lat, to_lon)

    def calculate_distance_fallback(self, from_lat, from_lon, to_lat, to_lon):
        """Fallback distance calculation using Haversine formula"""
        try:
            from math import radians, cos, sin, asin, sqrt
            
            from_lat, from_lon, to_lat, to_lon = map(radians, [from_lat, from_lon, to_lat, to_lon])
            
            dlat = to_lat - from_lat
            dlon = to_lon - from_lon
            a = sin(dlat/2)**2 + cos(from_lat) * cos(to_lat) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of earth in kilometers
            
            distance_km = c * r
            return Decimal(str(round(distance_km, 2)))
        except Exception as e:
            logging.error(f"Error in fallback distance calculation: {str(e)}")
            return Decimal('10.0')

    def calculate_total_distance_with_stops(self, from_lat, from_lon, to_lat, to_lon, stops_data=None):
        """Calculate total distance including all stops and return journey"""
        one_way_distance = Decimal('0.00')
        current_lat, current_lon = from_lat, from_lon
        
        # Calculate distance to each stop
        if stops_data:
            for stop in stops_data:
                stop_lat = float(stop['latitude'])
                stop_lon = float(stop['longitude'])
                
                segment_distance = self.calculate_distance_google_api(
                    current_lat, current_lon, stop_lat, stop_lon
                )
                one_way_distance += segment_distance
                
                current_lat, current_lon = stop_lat, stop_lon
        
        # Calculate distance from last stop (or origin if no stops) to final destination
        final_segment = self.calculate_distance_google_api(
            current_lat, current_lon, to_lat, to_lon
        )
        one_way_distance += final_segment
        
        # Always calculate as round trip (multiply by 2)
        total_distance = one_way_distance * 2
        
        return total_distance

    def calculate_nights_between_dates(self, start_date, end_date):
        """Calculate number of nights between two dates"""
        if not start_date or not end_date:
            return 0
        
        delta = end_date - start_date
        return max(0, delta.days)

    def calculate_trip_price(self, bus, user_search, start_date, end_date, stops_data=None):
        """Centralized method to calculate trip price based on new logic"""
        try:
            # Validate bus pricing data
            if not bus.base_price or bus.base_price <= 0:
                raise serializers.ValidationError("Bus base price is not properly configured.")
            
            if not bus.price_per_km or bus.price_per_km <= 0:
                raise serializers.ValidationError("Bus price per km is not properly configured.")

            # Get total distance including stops and return journey
            total_distance_km = self.calculate_total_distance_with_stops(
                user_search.from_lat, user_search.from_lon, 
                user_search.to_lat, user_search.to_lon,
                stops_data
            )
            
            # Calculate trip duration in days
            total_days = (end_date - start_date).days + 1 if end_date and start_date else 1
            
            # Bus pricing configuration
            base_price_per_day = bus.base_price  # Base price per day
            base_km_per_day = bus.base_price_km or Decimal('100')  # KM included per day (default 100)
            price_per_km = bus.price_per_km  # Rate for extra KM
            night_allowance = bus.night_allowance or Decimal('500')  # Driver allowance per night
            minimum_fare = bus.minimum_fare or Decimal('0.00')
            
            # Calculate base fare for total days
            base_fare = base_price_per_day * total_days
            
            # Calculate total included KM for the trip duration
            total_included_km = base_km_per_day * total_days
            
            # Calculate extra KM charges
            extra_km_charges = Decimal('0.00')
            if total_distance_km > total_included_km:
                extra_km = total_distance_km - total_included_km
                extra_km_charges = extra_km * price_per_km
            
            # Calculate nights and driver allowance
            nights = self.calculate_nights_between_dates(start_date, end_date)
            night_allowance_total = nights * night_allowance
            
            # Calculate total amount
            total_amount = base_fare + extra_km_charges + night_allowance_total
            
            # Ensure minimum fare is met
            if total_amount < minimum_fare:
                total_amount = minimum_fare
            
            return {
                'total_amount': total_amount,
                'total_distance_km': total_distance_km,
                'base_fare': base_fare,
                'extra_km_charges': extra_km_charges,
                'night_allowance_total': night_allowance_total,
                'total_days': total_days,
                'nights': nights,
                'total_included_km': total_included_km,
                'extra_km': max(Decimal('0.00'), total_distance_km - total_included_km)
            }
            
        except Exception as e:
            logging.error(f"Error calculating trip price: {str(e)}")
            raise serializers.ValidationError(f"Error calculating trip price: {str(e)}")
        
    def get_price(self, obj):
        """Calculate and return the trip price"""
        user = self.context['request'].user
        
        try:
            user_search = UserBusSearch.objects.get(user=user)
            
            if not user_search.to_lat or not user_search.to_lon:
                return "Select destination"
            
            if not user_search.pick_up_date:
                return "Select pickup date"
            
            start_date = user_search.pick_up_date
            end_date = user_search.return_date if user_search.return_date else start_date
            
            # Get stops data from user search
            stops_data = []
            search_stops = user_search.search_stops.all().order_by('stop_order')
            for stop in search_stops:
                stops_data.append({
                    'location_name': stop.location_name,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude
                })
            
            price_data = self.calculate_trip_price(obj.bus, user_search, start_date, end_date, stops_data)
            return float(price_data['total_amount'])
            
        except UserBusSearch.DoesNotExist:
            return "Search data not found"
        except Exception as e:
            logging.error(f"Error in get_price: {str(e)}")
            return "Price calculation error"

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)

        user = self.context['request'].user
        bus = validated_data.get('bus')
        stops_data = validated_data.pop('stops_data', [])

        # Validate bus
        if not bus:
            raise serializers.ValidationError("Bus selection is required.")

        # Get location data from UserBusSearch
        try:
            bus_search = UserBusSearch.objects.get(user=user)
            
            if not bus_search.from_lat or not bus_search.from_lon:
                raise serializers.ValidationError("Pickup location is required.")
            
            if not bus_search.to_lat or not bus_search.to_lon:
                raise serializers.ValidationError("Destination location is required.")
            
            if not bus_search.pick_up_date:
                raise serializers.ValidationError("Pickup date is required.")
                
        except UserBusSearch.DoesNotExist:
            logger.error(f"No bus search data found for user {user.id}")
            raise serializers.ValidationError("Bus search data not found. Please search for buses first.")

        # Get stops from user search if not provided in request
        if not stops_data:
            search_stops = bus_search.search_stops.all().order_by('stop_order')
            stops_data = []
            for stop in search_stops:
                stops_data.append({
                    'location_name': stop.location_name,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude
                })

        # Set dates and other data from search
        start_date = bus_search.pick_up_date
        end_date = validated_data.get('end_date')
        
        # Set end_date - use return_date if available, otherwise use start_date
        if bus_search.return_date:
            end_date = bus_search.return_date
        elif not end_date:
            end_date = start_date
        
        # Update validated_data - removed one_way field since we always calculate as round trip
        validated_data.update({
            'start_date': start_date,
            'end_date': end_date,
            'from_location': bus_search.from_location,
            'to_location': bus_search.to_location,
            'from_lat': bus_search.from_lat,
            'from_lon': bus_search.from_lon,
            'to_lat': bus_search.to_lat,
            'to_lon': bus_search.to_lon,
            'pick_up_time': bus_search.pick_up_time,
            'return_date': bus_search.return_date,
            'total_travelers': bus.capacity
        })

        # Calculate total amount using centralized method with stops
        price_data = self.calculate_trip_price(bus, bus_search, start_date, end_date, stops_data)
        
        # Update validated_data with calculated prices
        validated_data.update({
            'total_amount': price_data['total_amount'],
            'night_allowance_total': price_data['night_allowance_total'],
            'base_price_days': price_data['total_days'],  # Now represents total days
            'total_distance': price_data['total_distance_km']
        })

        logger.info(f"Trip calculation - Total Distance: {price_data['total_distance_km']} km, "
                   f"Total Days: {price_data['total_days']}, "
                   f"Base Fare: {price_data['base_fare']}, "
                   f"Extra KM Charges: {price_data['extra_km_charges']}, "
                   f"Nights: {price_data['nights']}, "
                   f"Night Allowance: {price_data['night_allowance_total']}, "
                   f"Total: {price_data['total_amount']}")

        # Calculate minimum advance amount required
        total_amount = validated_data.get('total_amount')
        advance_percent, min_advance_amount = get_advance_amount_from_db(total_amount)

        # Handle partial amount
        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            partial_amount = self.initial_data.get('partial_amount')

        if partial_amount is not None:
            try:
                partial_amount = Decimal(str(partial_amount))
                if partial_amount < min_advance_amount:
                    raise serializers.ValidationError(
                        f"Partial amount ({partial_amount}) must be greater than or equal to "
                        f"the minimum advance amount ({min_advance_amount})."
                    )
                validated_data['advance_amount'] = partial_amount
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid partial amount format.")
        else:
            validated_data['advance_amount'] = min_advance_amount

        # Calculate admin commission
        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        # Create booking
        booking = super().create(validated_data)

        # Create stops for the booking
        if stops_data:
            current_lat, current_lon = bus_search.from_lat, bus_search.from_lon
            
            for i, stop_data in enumerate(stops_data):
                stop_lat = float(stop_data['latitude'])
                stop_lon = float(stop_data['longitude'])
                
                # Calculate distance from previous point
                distance_from_previous = self.calculate_distance_google_api(
                    current_lat, current_lon, stop_lat, stop_lon
                )
                
                BusBookingStop.objects.create(
                    booking=booking,
                    stop_order=i + 1,
                    location_name=stop_data['location_name'],
                    latitude=stop_lat,
                    longitude=stop_lon,
                    distance_from_previous=distance_from_previous
                )
                
                current_lat, current_lon = stop_lat, stop_lon

        # Create admin commission record
        AdminCommission.objects.create(
            booking_type='bus',
            booking_id=booking.booking_id,
            advance_amount=validated_data['advance_amount'],
            commission_percentage=commission_percent,
            revenue_to_admin=revenue,
            original_revenue=revenue,
            referral_deduction=Decimal('0.00')
        )

        # Handle referral rewards (existing code remains the same)
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")

                referrer = None
                try:
                    referrer = User.objects.get(mobile=wallet.referred_by)
                except User.DoesNotExist:
                    try:
                        referrer = User.objects.get(email=wallet.referred_by)
                    except User.DoesNotExist:
                        referrer = User.objects.filter(mobile=wallet.referred_by).first()

                if referrer:
                    try:
                        referral_config = ReferAndEarn.objects.first()
                        reward_amount = referral_config.price if referral_config else Decimal('300.00')
                    except:
                        reward_amount = Decimal('300.00')

                    ReferralRewardTransaction.objects.create(
                        referrer=referrer,
                        referred_user=user,
                        booking_type='bus',
                        booking_id=booking.booking_id,
                        reward_amount=reward_amount,
                        status='pending'
                    )
                    wallet.referral_used = True
                    wallet.save()
                    logger.info(f"Referral reward created for referrer {referrer.id}")
                else:
                    logger.warning(f"Referrer not found: {wallet.referred_by}")
        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error in referral processing: {str(e)}")

        return booking
    

class SingleBusBookingSerializer(serializers.ModelSerializer):
    booking_type = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    bus_name = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    price_per_km = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    base_fare = serializers.SerializerMethodField()
    refunded_amount = serializers.SerializerMethodField()
    stops = BusBookingStopSerializer(many=True, read_only=True)

    class Meta:
        model = BusBooking
        fields = [
            'booking_id','tax' ,'total_distance','base_fare','from_location', 'refunded_amount','advance_amount','pick_up_time','to_location', 'start_date', 
            'end_date', 'total_travelers', 'total_amount', 'price_per_km',
            'paid_amount', 'bus_name', 'booking_type','one_way','trip_status','balance_amount','stops'
        ]

    def get_base_fare(self,obj):
        return obj.bus.minimum_fare

    def get_price_per_km(self, obj):
        return obj.bus.price_per_km
    
    def get_tax(self,obj):
        return 0
    
    def get_refunded_amount(self,obj):
        return 0

    def get_booking_type(self, obj):
        return "bus"
    
    def get_paid_amount(self, obj):
        return obj.advance_amount
    
    def get_bus_name(self, obj):
        return obj.bus.bus_name

    def get_end_date(self, obj):
        if obj.one_way:
            origin = obj.from_location
            destination = obj.to_location
            api_key = settings.GOOGLE_MAPS_API_KEY

            url = (
                f'https://maps.googleapis.com/maps/api/distancematrix/json'
                f'?origins={origin}&destinations={destination}'
                f'&mode=driving&key={api_key}'
            )
            
            try:
                response = requests.get(url)
                data = response.json()

                if data['status'] == 'OK':
                    element = data['rows'][0]['elements'][0]
                    if element['status'] == 'OK':
                        duration_seconds = element['duration']['value']
                        duration = timedelta(seconds=duration_seconds)
                        end_date = obj.start_date + duration
                        return end_date
            except Exception as e:
                print("Error getting travel time:", e)

            return obj.start_date
        else:
            return obj.return_date

from datetime import timedelta
from django.db.models import Count, Q

class SimplePlaceSerializer(serializers.Serializer):
    name = serializers.CharField()

class SimpleDayPlanSerializer(serializers.Serializer):
    day_number = serializers.IntegerField()
    places = SimplePlaceSerializer(many=True)

class SinglePackageBookingSerilizer(serializers.ModelSerializer):
    end_date = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    bus_name = serializers.SerializerMethodField()
    booking_type = serializers.SerializerMethodField()
    day_wise_plan = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    base_fare = serializers.SerializerMethodField()
    refunded_amount = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = [
            'booking_id','tax','base_fare','rooms','from_location','refunded_amount','advance_amount' ,'to_location',
            'start_date', 'end_date', 'total_travelers',
            'total_amount', 'paid_amount', 'bus_name',
            'booking_type', 'male', 'female', 'children',
            'day_wise_plan','trip_status','balance_amount'
        ]

    def get_base_fare(self,obj):
        buses = obj.package.buses.all()
        return [bus.minimum_fare for bus in buses]

    def get_tax(self,obj):
        return 0
    
    def get_refunded_amount(self,obj):
        return 0

    def get_end_date(self, obj):
        night_count = obj.package.day_plans.filter(night=True).count()
        total_days = obj.package.days + night_count
        end_date = obj.start_date + timedelta(days=total_days)
        return end_date

    def get_booking_type(self, obj):
        return "package"

    def get_paid_amount(self, obj):
        return obj.advance_amount

    def get_bus_name(self, obj):
        buses = obj.package.buses.all()
        return [bus.bus_name for bus in buses]

    def get_day_wise_plan(self, obj):
        day_plans = obj.package.day_plans.all().order_by('day_number')
        return SimpleDayPlanSerializer(day_plans, many=True).data


class PackageBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    partial_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        write_only=True,
        help_text="Amount user chooses to pay initially. Must be >= advance_amount."
    )

    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers',
            'partial_amount', 'booking_type', 'total_travelers', 'rooms','total_amount'
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields + ['rooms']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_package_details(self, obj):
        return PackageSerializer(obj.package).data

    def get_booking_type(self, obj):
        return "package"

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)

        # Calculate total amount first
        package = validated_data.get('package')
        total_travelers = validated_data.get('total_travelers', 0)
        
        if not package:
            raise serializers.ValidationError("Package is required")
        
        # Calculate total amount based on package price and travelers
        calculated_total_amount = total_travelers * package.price_per_person
        validated_data['total_amount'] = calculated_total_amount
        
        user = self.context['request'].user

        # REMOVED: Auto wallet balance application logic

        # Calculate advance amount
        advance_percent, min_advance_amount = get_advance_amount_from_db(calculated_total_amount)

        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            partial_amount = self.initial_data.get('partial_amount')

        if partial_amount:
            try:
                partial_amount = Decimal(str(partial_amount))
                if partial_amount < min_advance_amount:
                    raise serializers.ValidationError(
                        f"Partial amount ({partial_amount}) must be >= minimum advance amount ({min_advance_amount})."
                    )
                validated_data['advance_amount'] = partial_amount
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid partial amount format.")
        else:
            validated_data['advance_amount'] = min_advance_amount

        # Calculate rooms required
        rooms_required = (total_travelers + 2) // 3  # Ceiling of total_travelers / 3
        validated_data['rooms'] = rooms_required

        # Calculate commission
        commission_percent, revenue = get_admin_commission_from_db(calculated_total_amount)

        # Create the booking with all calculated values
        booking = super().create(validated_data)

        # Get referral reward amount
        try:
            referral_config = ReferAndEarn.objects.first()
            reward_amount = referral_config.price
        except:
            print("no amount error")

        # Create admin commission record (store original revenue)
        AdminCommission.objects.create(
            booking_type='package',
            booking_id=booking.booking_id,
            advance_amount=validated_data['advance_amount'],
            commission_percentage=commission_percent,
            revenue_to_admin=revenue,
            original_revenue=revenue,  # Store original revenue
            referral_deduction=Decimal('0.00')  # Will be updated when referral is credited
        )

        # Process referral rewards
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")
                referrer = User.objects.filter(
                    models.Q(mobile=wallet.referred_by) | models.Q(email=wallet.referred_by)
                ).first()

                if referrer:
                    try:
                        # Create referral reward transaction (will be credited only after trip completion)
                        ReferralRewardTransaction.objects.create(
                            referrer=referrer,
                            referred_user=user,
                            booking_type='package',
                            booking_id=booking.booking_id,
                            reward_amount=reward_amount,
                            status='pending'
                        )
                        wallet.referral_used = True
                        wallet.save()
                        logger.info(f"Created referral reward for referrer {referrer.id} from package booking {booking.booking_id}")
                    except Exception as e:
                        logger.error(f"Error creating referral transaction: {str(e)}")
                else:
                    logger.warning(f"Could not find referrer with identifier '{wallet.referred_by}'")
        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Unexpected error during referral processing: {str(e)}")

        return booking

class TravelerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a traveler associated with a booking"""
    booking_type = serializers.ChoiceField(choices=['bus', 'package'], write_only=True)
    booking_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'age', 'place', 
                 'dob', 'id_proof', 'email', 'mobile', 'city',
                 'booking_type', 'booking_id', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'created_at': {'read_only': True}
        }
    
    def validate(self, data):
        booking_type = data.pop('booking_type')
        booking_id = data.pop('booking_id')
        
        if booking_type == 'bus':
            try:
                booking = BusBooking.objects.get(booking_id=booking_id)
                data['bus_booking'] = booking
            except BusBooking.DoesNotExist:
                raise serializers.ValidationError(f"Bus booking with id {booking_id} does not exist")
        else:  # booking_type == 'package'
            try:
                booking = PackageBooking.objects.get(booking_id=booking_id)
                data['package_booking'] = booking
            except PackageBooking.DoesNotExist:
                raise serializers.ValidationError(f"Package booking with id {booking_id} does not exist")
        
        return data
    
    def create(self, validated_data):
        traveler = Travelers.objects.create(**validated_data)
        return traveler
    
class PackageFilterSerializer(serializers.ModelSerializer):
    package_name = serializers.SerializerMethodField()
    package_id = serializers.SerializerMethodField()
    package_images = serializers.SerializerMethodField()
    capacity = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    package_bus_name = serializers.SerializerMethodField()
    package_bus_id = serializers.SerializerMethodField()
    travels_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PackageBooking
        fields = ['booking_id','booking_status','package_name','total_travelers','start_date','total_amount','from_location',
                  'to_location','created_at','average_rating', 'total_reviews','package_images','capacity','package_bus_name','package_id','package_bus_id','travels_name']

    def get_package_name(self, obj):
        return obj.package.places
    
    def get_travels_name(self, obj):
        return obj.package.vendor.travels_name
    
    def get_package_id(self, obj):
        return obj.package.id
    
    def get_package_bus_id(self, obj):
        buses = obj.package.buses.all()
        return [bus.id for bus in buses]
    
    def get_package_bus_name(self, obj):
        buses = obj.package.buses.all()
        return [bus.bus_name for bus in buses]
    
    def get_capacity(self, obj):
        buses = obj.package.buses.all()
        total_capacity = sum(bus.capacity for bus in buses)
        return total_capacity

    
    def get_average_rating(self, obj):
        avg = obj.package.package_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.package.package_reviews.count()
    
    def get_package_images(self, obj):
        request = self.context.get('request')
        images = obj.package.package_images.all()
        return [request.build_absolute_uri(image.image.url) for image in images if image.image]
    
class BusFilterSerializer(serializers.ModelSerializer):
    bus_name = serializers.SerializerMethodField()
    bus_id = serializers.SerializerMethodField()
    bus_images = serializers.SerializerMethodField()
    capacity = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    travels_name = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = ['booking_id','booking_status','bus_name','total_travelers','start_date','total_amount','from_location',
                  'to_location','created_at','average_rating', 'total_reviews','bus_images','capacity','bus_id','travels_name']

    def get_bus_name(self, obj):
        return obj.bus.bus_name
    
    def get_travels_name(self, obj):
        return obj.bus.vendor.travels_name
    
    def get_bus_id(self, obj):
        return obj.bus.id
    
    def get_capacity(self,obj):
        return obj.bus.capacity

    def get_average_rating(self, obj):
        avg = obj.bus.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.bus.bus_reviews.count()
    
    def get_bus_images(self, obj):
        request = self.context.get('request')
        images = obj.bus.images.all()
        return [request.build_absolute_uri(image.bus_view_image.url) for image in images if image.bus_view_image]
    


class PackageImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageImage
        fields = ['id', 'image', 'uploaded_at']


class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ['id', 'image']


class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Place
        fields = ['id', 'name', 'description', 'images']


class StayImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StayImage
        fields = ['id', 'image']


class StaySerializer(serializers.ModelSerializer):
    images = StayImageSerializer(many=True, read_only=True)

    class Meta:
        model = Stay
        fields = ['id', 'hotel_name', 'description', 'location', 'is_ac', 'has_breakfast', 'images']


class MealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealImage
        fields = ['id', 'image']


class MealSerializer(serializers.ModelSerializer):
    images = MealImageSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = ['id', 'type', 'description', 'restaurant_name', 'location', 'time', 'images']


class ActivityImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityImage
        fields = ['id', 'image']


class ActivitySerializer(serializers.ModelSerializer):
    images = ActivityImageSerializer(many=True, read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'name', 'description', 'time', 'location', 'images']


class DayPlanSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True, read_only=True)
    stay = StaySerializer(read_only=True)
    meals = MealSerializer(many=True, read_only=True)
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta:
        model = DayPlan
        fields = ['id', 'day_number', 'description', 'places', 'stay', 'meals', 'activities']

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon']


class BusFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusFeature
        fields = ['id', 'name']


class BusImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusImage
        fields = '__all__'


class BusTravelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusTravelImage
        fields = ['id', 'image']


class BusDetailSerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    features = BusFeatureSerializer(many=True, read_only=True)
    images = BusImageSerializer(many=True, read_only=True)
    travel_images = BusTravelImageSerializer(many=True, read_only=True)

    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Bus
        fields = [
            'id', 'bus_name', 'bus_number', 'capacity', 'vehicle_description', 'vehicle_rc_number',
            'travels_logo', 'rc_certificate', 'license', 'contract_carriage_permit', 'passenger_insurance',
            'vehicle_insurance', 'base_price', 'price_per_km', 'minimum_fare', 'status',
            'amenities', 'features', 'images', 'travel_images',
            'average_rating', 'total_reviews'
        ]

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()

class BusMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = ['id', 'bus_name', 'bus_number']

class PackageSerializer(serializers.ModelSerializer):
    travels_name = serializers.SerializerMethodField()
    buses = BusMinimalSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()
    price_per_person = serializers.SerializerMethodField()
    night = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'header_image', 'places', 'days', 'night',
            'ac_available', 'guide_included', 'buses', 'bus_location',
            'price_per_person', 'travels_name', 'is_favorite'
        ]

    def get_night(self, obj):
        night_count = obj.day_plans.filter(night=True).count()
        return night_count

    def get_travels_name(self, obj):
        return obj.vendor.travels_name

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, package=obj).exists()
        return False

    def get_price_per_person(self, obj):
        return int(obj.price_per_person)
    
class PopularBusSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    bus_image = serializers.SerializerMethodField()

    class Meta:
        model = Bus
        fields = [
            'id',
            'bus_name',
            'capacity',
            'average_rating',
            'total_reviews',
            'is_popular',
            'is_favorite',
            'bus_image',  # 👈 include in output
        ]

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()
    
    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            exists = Favourite.objects.filter(user=request.user, bus=obj).exists()
            return exists
        return False


    def get_bus_image(self, obj):
        request = self.context.get('request')
        image = obj.images.first()
        if image and image.bus_view_image:
            if request:
                return request.build_absolute_uri(image.bus_view_image.url)
            return image.bus_view_image.url
        return None

class ListPackageSerializer(serializers.ModelSerializer):
    package_images = PackageImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    buses_location_data = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    travels_name = serializers.SerializerMethodField()
    night = serializers.SerializerMethodField()
    
    class Meta:
        model = Package
        fields = [
            'id',
            'header_image','package_images','places', 'days',
            'price_per_person',
            'average_rating', 'total_reviews', 'buses_location_data','is_favorite','travels_name',
            'bus_location','night'
        ]

    def get_night(self, obj):
        night_count = obj.day_plans.filter(night=True).count()
        return night_count

    def get_travels_name(self, obj):
        return obj.vendor.travels_name

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, package=obj).exists()
        return False

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()
    
    def get_buses_location_data(self, obj):
        """
        Return location data for all buses associated with this package
        """
        buses_data = []
        user_location = self.context.get('user_location')
        
        for bus in obj.buses.all():
            if bus.latitude is not None and bus.longitude is not None:
                bus_data = {
                    'id': bus.id,
                    'bus_name': bus.bus_name,
                    'bus_number': bus.bus_number,
                    'latitude': bus.latitude,
                    'longitude': bus.longitude,
                    'location': bus.location
                }
                
                # Calculate distance if user location is provided
                if user_location:
                    bus_coords = (bus.latitude, bus.longitude)
                    distance_km = geodesic(user_location, bus_coords).kilometers
                    bus_data['distance_km'] = round(distance_km, 1)
                
                buses_data.append(bus_data)
                
        return buses_data
    

class BusSerializer(serializers.ModelSerializer):
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    vendor_name = serializers.SerializerMethodField()
    amenities_list = serializers.SerializerMethodField()
    features_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Bus
        fields = [
            'id', 'bus_name', 'bus_number', 'capacity', 'vehicle_description',
            'bus_type', 'average_rating', 'total_reviews', 'vendor_name',
            'base_price', 'price_per_km', 'minimum_fare', 'status',
            'location', 'latitude', 'longitude', 'travels_logo',
            'amenities_list', 'features_list', 'is_popular'
        ]

    def get_vendor_name(self, obj):
        return obj.vendor
    
    def get_amenities_list(self, obj):
        return [
            {
                'id': amenity.id,
                'name': amenity.name,
                'description': amenity.description,
                'icon': self.context['request'].build_absolute_uri(amenity.icon.url) if amenity.icon else None
            } for amenity in obj.amenities.all()
        ]
    
    def get_features_list(self, obj):
        return [
            {
                'id': feature.id,
                'name': feature.name,
                'description': feature.description
            } for feature in obj.features.all()
        ]
    

class ListingUserPackageSerializer(serializers.ModelSerializer):
    package_images = PackageImageSerializer(many=True, read_only=True)
    day_plans = DayPlanSerializer(many=True, read_only=True)

    travels_name = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)
    buses = BusDetailSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()
    price_per_person = serializers.SerializerMethodField()
    extra_charge_per_km = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    night = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id','package_images','vendor_name', 'sub_category_name', 'header_image', 'places', 'days', 'night',
            'ac_available', 'guide_included', 'buses', 'bus_location', 'price_per_person',
            'extra_charge_per_km', 'status', 'average_rating', 'total_reviews',
            'day_plans', 'created_at', 'updated_at', 'travels_name', 'is_favorite'
        ]

    def get_travels_name(self, obj):
        return obj.vendor.travels_name
    
    def get_night(self, obj):
        night_count = obj.day_plans.filter(night=True).count()
        return night_count

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, package=obj).exists()
        return False

    def get_price_per_person(self, obj):
        return int(obj.price_per_person)

    def get_extra_charge_per_km(self, obj):
        return int(obj.extra_charge_per_km)

    def get_average_rating(self, obj):
        avg = obj.package_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.package_reviews.count()


class PackageBookingUpdateSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    room_count = serializers.SerializerMethodField(read_only=True)
    
    partial_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        write_only=True,
        help_text="Amount user chooses to pay initially. Must be >= advance_amount."
    )
    
    # Add trip_status field to allow updates
    trip_status = serializers.ChoiceField(
        choices=[
            ('not_started', 'Not Started'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        required=False,
        help_text="Status of the trip"
    )

    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers', 'total_travelers', 
            'partial_amount', 'booking_type', 'room_count', 'trip_status'
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data

    def get_booking_type(self, obj):
        return "package"

    def get_room_count(self, obj):  # ✅ Room calculation logic
        if obj.total_travelers is not None:
            return math.ceil(obj.total_travelers / 3)
        return 0

    def validate_trip_status(self, value):
        """
        Validate trip status transitions
        """
        instance = getattr(self, 'instance', None)
        if instance:
            current_status = instance.trip_status
            
            # Define valid transitions
            valid_transitions = {
                'not_started': ['ongoing', 'cancelled'],
                'ongoing': ['completed', 'cancelled'],
                'completed': [],  # No transitions from completed
                'cancelled': []   # No transitions from cancelled
            }
            
            if value != current_status and value not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot change trip status from '{current_status}' to '{value}'. "
                    f"Valid transitions from '{current_status}' are: {valid_transitions.get(current_status, [])}"
                )
        
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        user = self.context['request'].user
        total_amount = validated_data.get('total_amount', instance.total_amount)
        
        # Handle trip status update
        new_trip_status = validated_data.get('trip_status')
        if new_trip_status and new_trip_status != instance.trip_status:
            logger.info(f"Updating trip status from '{instance.trip_status}' to '{new_trip_status}' for booking {instance.booking_id}")

        if total_amount is None:
            raise serializers.ValidationError({"error": "Total amount cannot be None"})

        if 'total_amount' in validated_data:
            if total_amount <= 0:
                raise serializers.ValidationError({"error": "Total amount must be greater than zero"})

        if 'total_amount' in validated_data:
            try:
                wallet = Wallet.objects.get(user=user)
                if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                    if wallet.balance > total_amount:
                        raise serializers.ValidationError({"error": "Wallet balance cannot be greater than total amount"})

                    wallet_amount_used = wallet.balance
                    total_amount -= wallet_amount_used
                    validated_data['total_amount'] = total_amount

                    wallet.balance = Decimal('0.00')
                    wallet.save()

                    logger.info(f"Used wallet balance of {wallet_amount_used} for package booking update. New total: {total_amount}")
            except Wallet.DoesNotExist:
                logger.info(f"No wallet found for user {user.id}")
            except Exception as e:
                logger.error(f"Error processing wallet: {str(e)}")
                raise serializers.ValidationError({"error": f"Error processing wallet: {str(e)}"})

        if 'total_amount' in validated_data:
            advance_percent, min_advance_amount = get_advance_amount_from_db(total_amount)
        else:
            advance_percent, min_advance_amount = get_advance_amount_from_db(instance.total_amount)

        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            partial_amount = self.initial_data.get('partial_amount')

        if partial_amount:
            try:
                partial_amount = Decimal(str(partial_amount))
                if partial_amount <= 0:
                    raise serializers.ValidationError({"error": "Partial amount must be greater than zero"})
                if partial_amount < min_advance_amount:
                    raise serializers.ValidationError({
                        "error": f"Partial amount ({partial_amount}) must be greater than or equal to the minimum advance amount ({min_advance_amount})"
                    })
                validated_data['advance_amount'] = partial_amount
            except (ValueError, TypeError):
                raise serializers.ValidationError({"error": "Invalid partial amount format"})

        booking = super().update(instance, validated_data)

        # Send notification for trip status changes
        if new_trip_status and new_trip_status != instance.trip_status:
            package_name = booking.package.name if hasattr(booking.package, 'name') else "Tour package"
            status_messages = {
                'ongoing': f"Your trip for {package_name} has started! Have a wonderful journey. Booking ID: {booking.booking_id}",
                'completed': f"Your trip for {package_name} has been completed! We hope you had a great experience. Booking ID: {booking.booking_id}",
                'cancelled': f"Your booking for {package_name} has been cancelled. Booking ID: {booking.booking_id}"
            }
            
            if new_trip_status in status_messages:
                send_notification(
                    user=user,
                    message=status_messages[new_trip_status]
                )

        if 'total_amount' in validated_data:
            commission_percent, revenue = get_admin_commission_from_db(total_amount)
            try:
                admin_commission = AdminCommission.objects.get(booking_type='package', booking_id=booking.booking_id)
                admin_commission.advance_amount = booking.advance_amount
                admin_commission.commission_percentage = commission_percent
                admin_commission.revenue_to_admin = revenue
                admin_commission.save()
                logger.info(f"Updated admin commission for package booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                AdminCommission.objects.create(
                    booking_type='package',
                    booking_id=booking.booking_id,
                    advance_amount=booking.advance_amount,
                    commission_percentage=commission_percent,
                    revenue_to_admin=revenue
                )
                logger.info(f"Created admin commission for package booking {booking.booking_id}")

        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")

                referrer = None
                try:
                    referrer = User.objects.get(mobile=wallet.referred_by)
                except User.DoesNotExist:
                    try:
                        referrer = User.objects.get(email=wallet.referred_by)
                    except User.DoesNotExist:
                        referrer = User.objects.filter(mobile=wallet.referred_by).first()

                if referrer:
                    existing_reward = ReferralRewardTransaction.objects.filter(
                        referred_user=user,
                        booking_type='package',
                        booking_id=booking.booking_id
                    ).exists()

                    if not existing_reward:
                        reward = 300
                        try:
                            ReferralRewardTransaction.objects.create(
                                referrer=referrer,
                                referred_user=user,
                                booking_type='package',
                                booking_id=booking.booking_id,
                                reward_amount=reward,
                                status='pending'
                            )
                            wallet.referral_used = True
                            wallet.save()
                            logger.info(f"Created referral reward for referrer {referrer.id} from package booking update {booking.booking_id}")
                        except Exception as e:
                            logger.error(f"Error creating referral transaction: {str(e)}")
                            raise serializers.ValidationError({"error": f"Error creating referral transaction: {str(e)}"})
                else:
                    logger.warning(f"Could not find referrer with any identifier '{wallet.referred_by}'")
        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Unexpected error during referral processing: {str(e)}")
            raise serializers.ValidationError({"error": f"Unexpected error during referral processing: {str(e)}"})

        return booking


class BusListingSerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    features = BusFeatureSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    images = BusImageSerializer(many=True, read_only=True)
    bus_review_summary = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    price_per_km = serializers.SerializerMethodField()

    class Meta:
        model = Bus
        fields = [
            'id', 'bus_name', 'bus_number', 'location', 'price_per_km', 'capacity', 'base_price',
            'amenities', 'features', 'average_rating', 'total_reviews', 'is_favorite',
            'images', 'bus_review_summary', 'reviews', 'price'
        ]

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        if avg is None:
            return 2.0
        calculated_avg = round(avg, 1)
        return max(calculated_avg, 2.0)
    
    def get_price_per_km(self, obj):
        return f"{round(obj.price_per_km, 1):.1f}"

    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()

    def get_reviews(self, obj):
        reviews = obj.bus_reviews.all()
        return BusReviewSerializer(reviews, many=True).data

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, bus=obj).exists()
        return False

    def get_bus_review_summary(self, obj):
        bus_reviews = obj.bus_reviews
        average_rating = bus_reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
        total_reviews = bus_reviews.count()

        if total_reviews == 0:
            rating_breakdown = {f"{i}★": 0.0 for i in range(1, 6)}
            rating_breakdown["2★"] = 30.0
        else:
            rating_breakdown = {
                f"{i}★": round((bus_reviews.filter(rating=i).count() / total_reviews) * 100, 1)
                for i in range(1, 6)
            }
            if rating_breakdown["2★"] < 30.0:
                rating_breakdown["2★"] = 30.0

        final_average_rating = max(round(average_rating, 1), 2.0)

        return {
            "average_rating": final_average_rating,
            "total_reviews": total_reviews,
            "rating_breakdown": rating_breakdown
        }

    def get_price(self, obj):
        """Calculate and return the trip price"""
        request = self.context.get('request', None)
        if request and hasattr(request, 'user'):
            user = request.user
            try:
                user_search = UserBusSearch.objects.get(user=user)
                
                if not user_search or not user_search.to_lat or not user_search.to_lon:
                    return "Select destination"
                
                from decimal import Decimal
                from .views import BusListAPIView
                
                view = BusListAPIView()
                distance_km = view.calculate_distance_google_api(
                    user_search.from_lat, user_search.from_lon, 
                    user_search.to_lat, user_search.to_lon
                )
                
                seat_count = user_search.seat or 1
                base_price = obj.base_price or Decimal('0.00')
                base_price_km = obj.base_price_km or 0
                price_per_km = obj.price_per_km or Decimal('0.00')
                minimum_fare = obj.minimum_fare or Decimal('0.00')
                
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
                
                return float(total_amount)
                
            except UserBusSearch.DoesNotExist:
                return "Search data not found"
            except Exception as e:
                logging.error(f"Error in get_price: {str(e)}")
                return "Price calculation error"
        else:
            user = None

    def to_representation(self, instance):
        """Make base_price an integer in the output."""
        data = super().to_representation(instance)
        data['base_price'] = int(float(data['base_price'])) if data['base_price'] is not None else 0
        return data


# Response serializer for the bus list API view
class BusListResponseSerializer(serializers.Serializer):
    """
    Serializer for the complete bus list response including distance
    """
    distance_km = serializers.SerializerMethodField()
    buses = BusListingSerializer(many=True)
    
    def get_distance_km(self, obj):
        """Calculate distance from user's current location to destination in km"""
        try:
            user = self.context['request'].user
            user_search = UserBusSearch.objects.get(user=user)
            
            if not user_search.from_lat or not user_search.from_lon:
                return "User location not available"
            
            if not user_search.to_lat or not user_search.to_lon:
                return "Destination not selected"
            
            # Calculate distance using Google Distance Matrix API
            distance_km = self.calculate_distance_google_api(
                user_search.from_lat, user_search.from_lon,
                user_search.to_lat, user_search.to_lon
            )
            
            return f"{float(distance_km)} km"
            
        except UserBusSearch.DoesNotExist:
            return "Search data not found"
        except Exception as e:
            logging.error(f"Error calculating distance: {str(e)}")
            return "Distance calculation error"
    
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
            return Decimal('0.00')
    


class PackageDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageDriverDetail
        fields = '__all__'


class BusDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusDriverDetail
        fields = '__all__'


class FooterImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterImage
        fields = '__all__'

class FooterSectionSerializer(serializers.ModelSerializer):
    footer_images = FooterImagesSerializer(many=True, read_only=True)

    class Meta:
        model = FooterSection
        fields = ['id', 'main_image', 'footer_images', 'package', 'created_at']


class AdvertisementSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = Advertisement
        fields = ['id', 'title', 'subtitle', 'type', 'image', 'created_at']


class PackageSerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, write_only=True)
    buses = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), many=True)
    travels_name = serializers.SerializerMethodField()
    travels_location = serializers.SerializerMethodField()
    day_plans_read = DayPlanSerializer(source='dayplan_set', many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    price_per_person = serializers.SerializerMethodField()
    package_images = PackageImageSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = [
            'id',
            'sub_category', 'header_image', 'places', 'days',
            'ac_available', 'guide_included', 'buses', 
            'day_plans','day_plans_read','average_rating', 'total_reviews','price_per_person','is_favorite','travels_name','travels_location','package_images'
        ]
    
    def get_travels_name(self, obj):
        return obj.vendor.travels_name
    
    def get_travels_location(self, obj):
        return obj.vendor.location

    def get_price_per_person(self, obj):
        if obj.price_per_person is not None:
            return int(obj.price_per_person)
        return 0
    
    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favourite.objects.filter(user=request.user, package=obj).exists()
        return False
    
    def validate_days(self, value):
        if value <= 0:
            raise serializers.ValidationError("Days must be greater than 0.")
        return value

    def validate_nights(self, value):
        if value < 0:
            raise serializers.ValidationError("Nights cannot be negative.")
        return value
    

class UserBusSearchSerializer(serializers.ModelSerializer):
    pick_up_date = serializers.DateField(
        format='%d-%m-%Y',
        input_formats=['%d-%m-%Y'],
        required=False,
        allow_null=True
    )
    return_date = serializers.DateField(
        format='%d-%m-%Y',
        input_formats=['%d-%m-%Y'],
        required=False,
        allow_null=True
    )

    class Meta:
        model = UserBusSearch
        fields = '__all__'
        read_only_fields = ['user']
        extra_kwargs = {
            'to_lat': {'required': False, 'allow_null': True},
            'to_lon': {'required': False, 'allow_null': True},
            'seat': {'required': False, 'allow_null': True},
            'pick_up_time': {'required': False, 'allow_null': True},
            'pick_up_date': {'required': False, 'allow_null': True},
            'return_date': {'required': False, 'allow_null': True},
        }




class BusBookingUpdateSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    partial_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        write_only=True,
        help_text="Amount user chooses to pay initially. Must be >= advance_amount."
    )
    
    # Add trip_status field to allow updates
    trip_status = serializers.ChoiceField(
        choices=[
            ('not_started', 'Not Started'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        required=False,
        help_text="Status of the trip"
    )

    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way', 'travelers', 'booking_type', 
            'partial_amount', 'return_date', 'pick_up_time', 'price', 'trip_status'
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
            'total_amount': {'write_only': False, 'required': False}
        }

    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data
    
    def get_booking_type(self, obj):
        return "bus"

    def calculate_distance_google_api(self, from_lat, from_lon, to_lat, to_lon):
        """
        Calculate distance using Google Distance Matrix API
        Returns distance in kilometers
        """
        try:
            # Google Distance Matrix API endpoint
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            
            # API parameters
            params = {
                'origins': f"{from_lat},{from_lon}",
                'destinations': f"{to_lat},{to_lon}",
                'units': 'metric',
                'mode': 'driving',
                'key': settings.GOOGLE_DISTANCE_MATRIX_API_KEY  # Add this to your settings
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

    def get_price(self, obj):
        """Calculate and return the trip price"""
        try:
            # Use existing booking coordinates for price calculation
            from_lat = obj.from_lat
            from_lon = obj.from_lon
            to_lat = obj.to_lat
            to_lon = obj.to_lon
            
            if not all([from_lat, from_lon, to_lat, to_lon]):
                return "Location data missing"
            
            # Calculate distance
            distance_km = self.calculate_distance_google_api(from_lat, from_lon, to_lat, to_lon)
            
            # Get pricing details from bus
            seat_count = obj.total_travelers or 1
            base_price = obj.bus.base_price or Decimal('0.00')
            base_price_km = obj.bus.base_price_km or 0
            price_per_km = obj.bus.price_per_km or Decimal('0.00')
            minimum_fare = obj.bus.minimum_fare or Decimal('0.00')
            
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
            
            return float(total_amount)
            
        except Exception as e:
            logging.error(f"Error in get_price: {str(e)}")
            return "Price calculation error"

    def validate_trip_status(self, value):
        """
        Validate trip status transitions
        """
        instance = getattr(self, 'instance', None)
        if instance:
            current_status = instance.trip_status
            
            # Define valid transitions
            valid_transitions = {
                'not_started': ['ongoing', 'cancelled'],
                'ongoing': ['completed', 'cancelled'],
                'completed': [],  # No transitions from completed
                'cancelled': []   # No transitions from cancelled
            }
            
            if value != current_status and value not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot change trip status from '{current_status}' to '{value}'. "
                    f"Valid transitions from '{current_status}' are: {valid_transitions.get(current_status, [])}"
                )
        
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        user = self.context['request'].user
        total_amount = validated_data.get('total_amount', instance.total_amount)
        
        # Handle trip status update
        new_trip_status = validated_data.get('trip_status')
        if new_trip_status and new_trip_status != instance.trip_status:
            logger.info(f"Updating trip status from '{instance.trip_status}' to '{new_trip_status}' for booking {instance.booking_id}")

        if total_amount is None:
            raise serializers.ValidationError({"error": "Total amount cannot be None"})

        if 'total_amount' in validated_data:
            if total_amount <= 0:
                raise serializers.ValidationError({"error": "Total amount must be greater than zero"})

        # Handle wallet balance application
        if 'total_amount' in validated_data:
            try:
                wallet = Wallet.objects.get(user=user)
                if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                    if wallet.balance > total_amount:
                        raise serializers.ValidationError({"error": "Wallet balance cannot be greater than total amount"})

                    wallet_amount_used = wallet.balance
                    total_amount -= wallet_amount_used
                    validated_data['total_amount'] = total_amount

                    wallet.balance = Decimal('0.00')
                    wallet.save()

                    logger.info(f"Used wallet balance of {wallet_amount_used} for bus booking update. New total: {total_amount}")
            except Wallet.DoesNotExist:
                logger.info(f"No wallet found for user {user.id}")
            except Exception as e:
                logger.error(f"Error processing wallet: {str(e)}")
                raise serializers.ValidationError({"error": f"Error processing wallet: {str(e)}"})

        # Calculate advance amount
        if 'total_amount' in validated_data:
            advance_percent, min_advance_amount = get_advance_amount_from_db(total_amount)
        else:
            advance_percent, min_advance_amount = get_advance_amount_from_db(instance.total_amount)

        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            partial_amount = self.initial_data.get('partial_amount')

        if partial_amount:
            try:
                partial_amount = Decimal(str(partial_amount))
                if partial_amount <= 0:
                    raise serializers.ValidationError({"error": "Partial amount must be greater than zero"})
                if partial_amount < min_advance_amount:
                    raise serializers.ValidationError({
                        "error": f"Partial amount ({partial_amount}) must be greater than or equal to the minimum advance amount ({min_advance_amount})"
                    })
                validated_data['advance_amount'] = partial_amount
            except (ValueError, TypeError):
                raise serializers.ValidationError({"error": "Invalid partial amount format"})

        booking = super().update(instance, validated_data)

        # Send notification for trip status changes
        if new_trip_status and new_trip_status != instance.trip_status:
            bus_name = booking.bus.name if hasattr(booking.bus, 'name') else "Bus"
            route_info = f"from {booking.from_location} to {booking.to_location}" if booking.from_location and booking.to_location else ""
            
            status_messages = {
                'ongoing': f"Your bus trip {bus_name} {route_info} has started! Have a safe journey. Booking ID: {booking.booking_id}",
                'completed': f"Your bus trip {bus_name} {route_info} has been completed! We hope you had a comfortable journey. Booking ID: {booking.booking_id}",
                'cancelled': f"Your bus booking {bus_name} {route_info} has been cancelled. Booking ID: {booking.booking_id}"
            }
            
            if new_trip_status in status_messages:
                send_notification(
                    user=user,
                    message=status_messages[new_trip_status]
                )

        # Update admin commission if total amount changed
        if 'total_amount' in validated_data:
            commission_percent, revenue = get_admin_commission_from_db(total_amount)
            try:
                admin_commission = AdminCommission.objects.get(booking_type='bus', booking_id=booking.booking_id)
                admin_commission.advance_amount = booking.advance_amount
                admin_commission.commission_percentage = commission_percent
                admin_commission.revenue_to_admin = revenue
                admin_commission.save()
                logger.info(f"Updated admin commission for bus booking {booking.booking_id}")
            except AdminCommission.DoesNotExist:
                AdminCommission.objects.create(
                    booking_type='bus',
                    booking_id=booking.booking_id,
                    advance_amount=booking.advance_amount,
                    commission_percentage=commission_percent,
                    revenue_to_admin=revenue
                )
                logger.info(f"Created admin commission for bus booking {booking.booking_id}")

        # Handle referral processing (if not already processed)
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")

                referrer = None
                try:
                    referrer = User.objects.get(mobile=wallet.referred_by)
                except User.DoesNotExist:
                    try:
                        referrer = User.objects.get(email=wallet.referred_by)
                    except User.DoesNotExist:
                        referrer = User.objects.filter(mobile=wallet.referred_by).first()

                if referrer:
                    existing_reward = ReferralRewardTransaction.objects.filter(
                        referred_user=user,
                        booking_type='bus',
                        booking_id=booking.booking_id
                    ).exists()

                    if not existing_reward:
                        reward = 300
                        try:
                            ReferralRewardTransaction.objects.create(
                                referrer=referrer,
                                referred_user=user,
                                booking_type='bus',
                                booking_id=booking.booking_id,
                                reward_amount=reward,
                                status='pending'
                            )
                            wallet.referral_used = True
                            wallet.save()
                            logger.info(f"Created referral reward for referrer {referrer.id} from bus booking update {booking.booking_id}")
                        except Exception as e:
                            logger.error(f"Error creating referral transaction: {str(e)}")
                            raise serializers.ValidationError({"error": f"Error creating referral transaction: {str(e)}"})
                else:
                    logger.warning(f"Could not find referrer with any identifier '{wallet.referred_by}'")
        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Unexpected error during referral processing: {str(e)}")
            raise serializers.ValidationError({"error": f"Unexpected error during referral processing: {str(e)}"})

        return booking
    


class PackageSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageSubCategory
        fields = ['id', 'name', 'image']












class PayoutHistorySerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name')
    vendor_email = serializers.CharField(source='vendor.user.email')
    vendor_phone = serializers.CharField(source='vendor.phone_no')
    bookings = serializers.SerializerMethodField()
    bank_details = serializers.SerializerMethodField()

    class Meta:
        model = PayoutHistory
        fields = [
            'id',
            'payout_date',
            'vendor_name',
            'vendor_email',
            'vendor_phone',
            'payout_mode',
            'payout_reference',
            'total_amount',
            'admin_commission',
            'net_amount',
            'note',
            'bookings',
            'bank_details'
        ]

    def get_bookings(self, obj):
        bookings = []
        for pb in obj.bookings.all():
            bookings.append({
                'type': pb.booking_type,
                'booking_id': pb.booking_id,
                'amount': pb.amount,
                'commission': pb.commission
            })
        return bookings

    def get_bank_details(self, obj):
        try:
            bank = obj.vendor.bank_detail
            return {
                'account_number': bank.account_number,
                'ifsc_code': bank.ifsc_code,
                'holder_name': bank.holder_name,
                'payout_mode': bank.payout_mode
            }
        except VendorBankDetail.DoesNotExist:
            return None
        





class  TripStatusUpdateSerializer(serializers.Serializer):
    booking_type = serializers.ChoiceField(choices=['bus', 'package'])
    booking_id = serializers.IntegerField()
    
    def validate(self, data):
        booking_type = data['booking_type']
        booking_id = data['booking_id']
        
        # Get the appropriate model based on booking type
        if booking_type == 'bus':
            model_class = BusBooking
        elif booking_type == 'package':
            model_class = PackageBooking
        else:
            raise serializers.ValidationError("Invalid booking type")
        
        # Check if booking exists
        try:
            booking = model_class.objects.get(booking_id=booking_id)
        except model_class.DoesNotExist:
            raise serializers.ValidationError(f"{booking_type.title()} booking with ID {booking_id} not found")
        
        # Check if trip can be completed (must be ongoing)
        if booking.trip_status != 'ongoing':
            raise serializers.ValidationError(
                f"Trip status is currently '{booking.get_trip_status_display()}'. "
                "Only ongoing trips can be marked as completed."
            )
        
        # Check if booking is accepted
        if booking.booking_status != 'accepted':
            raise serializers.ValidationError(
                "Booking must be accepted before trip can be completed"
            )
        
        data['booking'] = booking
        return data