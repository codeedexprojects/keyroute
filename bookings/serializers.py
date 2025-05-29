
from rest_framework import serializers
from .models import BusBooking, PackageBooking, Travelers, UserBusSearch, PackageDriverDetail
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


User = get_user_model()

# Minimum wallet amount required for using wallet balance
MINIMUM_WALLET_AMOUNT = Decimal('1000.00')

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
        fields = ['booking_id', 'user', 'start_date', 'total_amount', 'advance_amount', 
                 'payment_status', 'booking_status', 'trip_status', 'created_at', 
                 'balance_amount', 'cancelation_reason', 'total_travelers', 
                 'male', 'female', 'children', 'from_location', 'to_location']
        read_only_fields = ['id', 'created_at', 'balance_amount']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

import requests
import logging
from decimal import Decimal
from django.conf import settings

class BusBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()

    # Partial payment field
    partial_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        write_only=True,
        help_text="Amount user chooses to pay initially. Must be >= advance_amount."
    )

    # Location fields are now read from UserBusSearch model
    # No need to pass them in the serializer

    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way', 'travelers', 'booking_type', 
            'partial_amount'
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
            'total_amount':{'write_only': False, 'required': False}
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

    def calculate_total_amount(self, bus, distance_km, seat_count):
        """
        Calculate total amount based on distance and bus pricing
        """
        try:
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
            logging.error(f"Error calculating total amount: {str(e)}")
            raise serializers.ValidationError("Error calculating trip amount. Please try again.")

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)

        # Get user and bus
        user = self.context['request'].user
        bus = validated_data.get('bus')

        # Get location data from UserBusSearch
        try:
            bus_search = UserBusSearch.objects.get(user=user)
            from_lat = bus_search.from_lat
            from_lon = bus_search.from_lon
            to_lat = bus_search.to_lat
            to_lon = bus_search.to_lon
            seat_count = bus_search.seat
        except UserBusSearch.DoesNotExist:
            logger.error(f"No bus search data found for user {user.id}")
            raise serializers.ValidationError("Bus search data not found. Please search for buses first.")

        # Calculate distance using Google Distance Matrix API
        distance_km = self.calculate_distance_google_api(from_lat, from_lon, to_lat, to_lon)
        logger.info(f"Calculated distance: {distance_km} km")

        # Calculate total amount based on distance and bus pricing
        calculated_total = self.calculate_total_amount(bus, distance_km, seat_count)
        validated_data['total_amount'] = calculated_total
        
        # Add location data to validated_data for saving in booking
        validated_data['from_lat'] = from_lat
        validated_data['from_lon'] = from_lon
        validated_data['to_lat'] = to_lat
        validated_data['to_lon'] = to_lon

        logger.info(f"Calculated total amount: {calculated_total} for distance: {distance_km} km")

        # Get the total amount from validated data
        total_amount = validated_data.get('total_amount')
        user = self.context['request'].user

        # Apply wallet balance if available
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                wallet_amount_used = wallet.balance
                total_amount -= wallet_amount_used
                validated_data['total_amount'] = total_amount

                # Update wallet balance
                wallet.balance = Decimal('0.00')
                wallet.save()

                logger.info(f"Used wallet balance of {wallet_amount_used} for booking. New total: {total_amount}")
        except Wallet.DoesNotExist:
            logger.info(f"No wallet found for user {user.id}")
        except Exception as e:
            logger.error(f"Error processing wallet: {str(e)}")

        # Calculate minimum advance amount required
        advance_percent, min_advance_amount = get_advance_amount_from_db(total_amount)

        # Get partial amount from request data
        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            partial_amount = self.initial_data.get('partial_amount')

        # Validate and set advance amount
        if partial_amount is not None:
            try:
                partial_amount = Decimal(str(partial_amount))
                if partial_amount < min_advance_amount:
                    raise serializers.ValidationError(
                        f"Partial amount ({partial_amount}) must be greater than or equal to the minimum advance amount ({min_advance_amount})."
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

        # Get referral reward amount (default to 300 if not set in ReferAndEarn model)
        try:
            referral_config = ReferAndEarn.objects.first()
            reward_amount = referral_config.price
        except:
            print("no amount error")

        # Create admin commission record (store original revenue)
        AdminCommission.objects.create(
            booking_type='bus',
            booking_id=booking.booking_id,
            advance_amount=validated_data['advance_amount'],
            commission_percentage=commission_percent,
            revenue_to_admin=revenue,
            original_revenue=revenue,  # Store original revenue
            referral_deduction=Decimal('0.00')  # Will be updated when referral is credited
        )

        # Process referral if applicable
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
                    # Create referral reward transaction (will be credited only after trip completion)
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

    class Meta:
        model = BusBooking
        fields = [
            'booking_id', 'from_location', 'to_location', 'start_date', 
            'end_date', 'total_travelers', 'total_amount', 
            'paid_amount', 'bus_name', 'booking_type'
        ]

    def get_booking_type(self, obj):
        return "bus"
    
    def get_paid_amount(self, obj):
        return obj.advance_amount
    
    def get_bus_name(self, obj):
        return obj.bus.bus_name

    def get_end_date(self, obj):
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

    class Meta:
        model = PackageBooking
        fields = [
            'booking_id','rooms','from_location', 'to_location',
            'start_date', 'end_date', 'total_travelers',
            'total_amount', 'paid_amount', 'bus_name',
            'booking_type', 'male', 'female', 'children',
            'day_wise_plan'
        ]

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

        # Apply wallet balance if available
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                wallet_amount_used = wallet.balance
                calculated_total_amount -= wallet_amount_used
                validated_data['total_amount'] = calculated_total_amount

                wallet.balance = Decimal('0.00')
                wallet.save()

                logger.info(f"Used wallet balance of {wallet_amount_used} for package booking. New total: {calculated_total_amount}")
        except Wallet.DoesNotExist:
            logger.info(f"No wallet found for user {user.id}")
        except Exception as e:
            logger.error(f"Error processing wallet: {str(e)}")

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
        fields = ['booking_id','package_name','total_travelers','start_date','total_amount','from_location',
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
        fields = ['booking_id','bus_name','total_travelers','start_date','total_amount','from_location',
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
            return Favourite.objects.filter(user=request.user, bus=obj).exists()
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
            'header_image', 'places', 'days',
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
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
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

    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers', 'total_travelers', 'partial_amount', 'booking_type', 'room_count'
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

    @transaction.atomic
    def update(self, instance, validated_data):
        user = self.context['request'].user
        total_amount = validated_data.get('total_amount', instance.total_amount)

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
    reviews = serializers.SerializerMethodField()  # Fix here

    class Meta:
        model = Bus
        fields = [
            'id', 'bus_name', 'bus_number', 'location','price_per_km', 'capacity', 'base_price',
            'amenities', 'features', 'average_rating', 'total_reviews', 'is_favorite',
            'images', 'bus_review_summary', 'reviews'
        ]

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

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
        else:
            rating_breakdown = {
                f"{i}★": round((bus_reviews.filter(rating=i).count() / total_reviews) * 100, 1)
                for i in range(1, 6)
            }

        return {
            "average_rating": round(average_rating, 1),
            "total_reviews": total_reviews,
            "rating_breakdown": rating_breakdown
        }

    def to_representation(self, instance):
        """Make base_price an integer in the output."""
        data = super().to_representation(instance)
        data['base_price'] = int(float(data['base_price'])) if data['base_price'] is not None else 0
        return data
    


class PackageDriverDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageDriverDetail
        fields = '__all__'


class FooterSectionSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)
    class Meta:
        model = FooterSection
        fields = ['id', 'image', 'package', 'created_at']


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
    class Meta:
        model = UserBusSearch
        fields = '__all__'
        read_only_fields = ['user']