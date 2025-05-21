
from rest_framework import serializers
from .models import BusBooking, PackageBooking, Travelers, BusDriverDetail, PackageDriverDetail
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

class BusBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    first_time_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

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
            'bus', 'bus_details', 'one_way', 'travelers', 'booking_type', 'partial_amount', 'first_time_discount'
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data
    
    def get_booking_type(self, obj):
        return "bus"

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)

        # Get the total amount from validated data
        total_amount = validated_data.get('total_amount')
        user = self.context['request'].user

        # Check if this is the user's first booking
        first_time_booking = False
        first_time_discount = Decimal('0.00')
        
        # Check if user has any previous bookings
        bus_bookings = BusBooking.objects.filter(user=user).exists()
        package_bookings = PackageBooking.objects.filter(user=user).exists()
        
        if not bus_bookings and not package_bookings:
            # This is the first booking for this user
            first_time_booking = True
            # Apply 10% discount
            first_time_discount = Decimal(str(total_amount)) * Decimal('0.10')
            total_amount -= first_time_discount
            validated_data['total_amount'] = total_amount
            validated_data['first_time_discount'] = first_time_discount
            
            logger.info(f"Applied first-time booking discount of {first_time_discount} for user {user.id}. New total: {total_amount}")

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
            # Try to get from initial data if not in validated_data
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
            # If not provided, default to minimum advance
            validated_data['advance_amount'] = min_advance_amount

        # Calculate admin commission
        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        # Create booking
        booking = super().create(validated_data)

        # Create admin commission record
        AdminCommission.objects.create(
            booking_type='bus',
            booking_id=booking.id,
            advance_amount=validated_data['advance_amount'],
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
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
                    reward = 300
                    ReferralRewardTransaction.objects.create(
                        referrer=referrer,
                        referred_user=user,
                        booking_type='bus',
                        booking_id=booking.id,
                        reward_amount=reward,
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

class SinglePackageBookingSerilizer(serializers.ModelSerializer):
    end_date = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    bus_name = serializers.SerializerMethodField()
    booking_type = serializers.SerializerMethodField()

    class Meta:
        model = PackageBooking
        fields = [
            'booking_id', 'from_location', 'to_location',
            'start_date', 'end_date', 'total_travelers',
            'total_amount', 'paid_amount', 'bus_name', 'booking_type'
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


class PackageBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    booking_type = serializers.SerializerMethodField()
    first_time_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    # Partial payment field  
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
            'package', 'package_details', 'travelers', 'partial_amount', 'booking_type', 'first_time_discount'
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

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)

        # Get the total amount from validated data
        total_amount = validated_data.get('total_amount')
        user = self.context['request'].user

        # Check if this is the user's first booking
        first_time_booking = False
        first_time_discount = Decimal('0.00')
        
        # Check if user has any previous bookings
        bus_bookings = BusBooking.objects.filter(user=user).exists()
        package_bookings = PackageBooking.objects.filter(user=user).exists()
        
        if not bus_bookings and not package_bookings:
            # This is the first booking for this user
            first_time_booking = True
            # Apply 10% discount
            first_time_discount = Decimal(str(total_amount)) * Decimal('0.10')
            total_amount -= first_time_discount
            validated_data['total_amount'] = total_amount
            validated_data['first_time_discount'] = first_time_discount
            
            logger.info(f"Applied first-time booking discount of {first_time_discount} for user {user.id}. New total: {total_amount}")

        # Apply wallet balance if available
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                wallet_amount_used = wallet.balance
                total_amount = total_amount - wallet_amount_used
                validated_data['total_amount'] = total_amount

                # Update wallet balance
                wallet.balance = Decimal('0.00')
                wallet.save()

                logger.info(f"Used wallet balance of {wallet_amount_used} for package booking. New total: {total_amount}")
        except Wallet.DoesNotExist:
            logger.info(f"No wallet found for user {user.id}")
        except Exception as e:
            logger.error(f"Error processing wallet: {str(e)}")

        # Calculate minimum advance amount required
        advance_percent, min_advance_amount = get_advance_amount_from_db(total_amount)

        # Get partial amount from validated data or initial data
        partial_amount = validated_data.pop('partial_amount', None)
        if partial_amount is None:
            # Try to get from initial data if not in validated_data
            partial_amount = self.initial_data.get('partial_amount')

        # Validate and set advance amount
        if partial_amount:
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
            # If not provided, default to minimum advance
            validated_data['advance_amount'] = min_advance_amount

        # Calculate admin commission
        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        # Create booking
        booking = super().create(validated_data)

        # Create admin commission record
        AdminCommission.objects.create(
            booking_type='package',
            booking_id=booking.id,
            advance_amount=validated_data['advance_amount'],
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
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
                    reward = 300
                    try:
                        ReferralRewardTransaction.objects.create(
                            referrer=referrer,
                            referred_user=user,
                            booking_type='package',
                            booking_id=booking.id,
                            reward_amount=reward,
                            status='pending'
                        )
                        wallet.referral_used = True
                        wallet.save()
                        logger.info(f"Created referral reward for referrer {referrer.id} from package booking {booking.id}")
                    except Exception as e:
                        logger.error(f"Error creating referral transaction: {str(e)}")
                else:
                    logger.warning(f"Could not find referrer with any identifier '{wallet.referred_by}'")
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
                booking = BusBooking.objects.get(id=booking_id)
                data['bus_booking'] = booking
            except BusBooking.DoesNotExist:
                raise serializers.ValidationError(f"Bus booking with id {booking_id} does not exist")
        else:  # booking_type == 'package'
            try:
                booking = PackageBooking.objects.get(id=booking_id)
                data['package_booking'] = booking
            except PackageBooking.DoesNotExist:
                raise serializers.ValidationError(f"Package booking with id {booking_id} does not exist")
        
        return data
    
    def create(self, validated_data):
        traveler = Travelers.objects.create(**validated_data)
        
        # Update the total_travelers count for package bookings
        if hasattr(traveler, 'package_booking') and traveler.package_booking:
            traveler.package_booking.total_travelers = \
                traveler.package_booking.travelers.count()
            traveler.package_booking.save()
            
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
        fields = ['id', 'bus_view_image']


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

    class Meta:
        model = Bus
        fields = ['id','bus_name','capacity','average_rating','total_reviews','is_popular']

    def get_average_rating(self, obj):
        avg = obj.bus_reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else 0.0

    def get_total_reviews(self, obj):
        return obj.bus_reviews.count()
    

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