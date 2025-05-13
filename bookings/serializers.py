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
        fields = ['id', 'user', 'start_date', 'total_amount', 'advance_amount', 
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

    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way', 'travelers',
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        total_amount = validated_data.get('total_amount')
        user = self.context['request'].user
        
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= MINIMUM_WALLET_AMOUNT:

                wallet_amount_used = wallet.balance

                total_amount = total_amount - wallet_amount_used
                validated_data['total_amount'] = total_amount
                
                wallet.balance = Decimal('0.00')
                wallet.save()
                
                logger.info(f"Used wallet balance of {wallet_amount_used} for bus booking. New total: {total_amount}")
        except Wallet.DoesNotExist:
            logger.info(f"No wallet found for user {user.id}")
            pass
        except Exception as e:
            logger.error(f"Error processing wallet: {str(e)}")
            
        advance_percent, advance_amount = get_advance_amount_from_db(total_amount)
        validated_data['advance_amount'] = advance_amount

        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        booking = super().create(validated_data)

        AdminCommission.objects.create(
            booking_type='bus',
            booking_id=booking.id,
            advance_amount=advance_amount,
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
        )

        try:
            wallet = Wallet.objects.get(user=user)
            
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")
                
                try:
                    referrer = User.objects.get(mobile=wallet.referred_by)
                except User.DoesNotExist:
                    try:
                        referrer = User.objects.get(email=wallet.referred_by)
                    except User.DoesNotExist:
                        try:
                            referrer = User.objects.filter(mobile=wallet.referred_by).first()
                        except:
                            logger.warning(f"Referrer with identifier '{wallet.referred_by}' not found")
                            return booking
                
                if referrer:
                    reward = 300
                    
                    try:
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
                        
                        logger.info(f"Created referral reward for referrer {referrer.id} from booking {booking.id}")
                    except Exception as e:
                        logger.error(f"Error creating referral transaction: {str(e)}")
                else:
                    logger.warning(f"Could not find referrer with any identifier '{wallet.referred_by}'")
        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Unexpected error during referral processing: {str(e)}")

        return booking


class PackageBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers',
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }
    
    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data

    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        total_amount = validated_data.get('total_amount')
        user = self.context['request'].user
        
        # Check if wallet has minimum balance and apply it to the booking
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= MINIMUM_WALLET_AMOUNT:
                wallet_amount_used = wallet.balance

                total_amount = total_amount - wallet_amount_used

                validated_data['total_amount'] = total_amount
                
                wallet.balance = Decimal('0.00')
                wallet.save()
                
                logger.info(f"Used wallet balance of {wallet_amount_used} for package booking. New total: {total_amount}")
        except Wallet.DoesNotExist:
            logger.info(f"No wallet found for user {user.id}")
            pass
        except Exception as e:
            logger.error(f"Error processing wallet: {str(e)}")

        advance_percent, advance_amount = get_advance_amount_from_db(total_amount)
        validated_data['advance_amount'] = advance_amount

        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        booking = super().create(validated_data)

        AdminCommission.objects.create(
            booking_type='package',
            booking_id=booking.id,
            advance_amount=advance_amount,
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
        )

        try:
            wallet = Wallet.objects.get(user=user)
            
            if wallet.referred_by and not wallet.referral_used:
                logger.info(f"Processing referral for user {user.id}, referred by {wallet.referred_by}")
                
                try:
                    referrer = User.objects.get(mobile=wallet.referred_by)
                except User.DoesNotExist:
                    try:
                        referrer = User.objects.get(email=wallet.referred_by)
                    except User.DoesNotExist:
                        try:
                            referrer = User.objects.filter(mobile=wallet.referred_by).first()
                        except:
                            logger.warning(f"Referrer with identifier '{wallet.referred_by}' not found")
                            return booking
                
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
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    package_images = serializers.SerializerMethodField()
    
    class Meta:
        model = PackageBooking
        fields = ['package_name','total_travelers','start_date','total_amount','id','from_location',
                  'to_location','created_at','average_rating', 'total_reviews','package_images']

    def get_package_name(self, obj):
        return obj.package.places
    
    def get_average_rating(self, obj):
        from reviews.models import BusReview
        avg = BusReview.objects.filter(bus=obj).aggregate(models.Avg('rating'))['rating__avg']
        return round(avg, 1) if avg is not None else 0.0
    
    def get_total_reviews(self, obj):
        from reviews.models import BusReview
        return BusReview.objects.filter(bus=obj).count()
    
    def get_package_images(self, obj):
        request = self.context.get('request')
        images = obj.package.package_images.all()
        return [request.build_absolute_uri(image.image.url) for image in images if image.image]
    
class BusFilterSerializer(serializers.ModelSerializer):
    bus_name = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    bus_images = serializers.SerializerMethodField()

    class Meta:
        model = BusBooking
        fields = ['bus_name','total_travelers','start_date','total_amount','id','from_location',
                  'to_location','created_at','average_rating', 'total_reviews','bus_images']

    def get_bus_name(self, obj):
        return obj.bus.bus_name

    def get_average_rating(self, obj):
        from reviews.models import BusReview
        avg = BusReview.objects.filter(bus=obj).aggregate(models.Avg('rating'))['rating__avg']
        return round(avg, 1) if avg is not None else 0.0
    
    def get_total_reviews(self, obj):
        from reviews.models import BusReview
        return BusReview.objects.filter(bus=obj).count()
    
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


class PackageSerializer(serializers.ModelSerializer):
    package_images = PackageImageSerializer(many=True, read_only=True)
    day_plans = DayPlanSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)

    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)
    buses = serializers.StringRelatedField(many=True)

    class Meta:
        model = Package
        fields = [
            'id', 'vendor_name', 'sub_category_name', 'header_image', 'places', 'days', 'nights',
            'ac_available', 'guide_included', 'buses', 'bus_location', 'price_per_person',
            'extra_charge_per_km', 'status', 'average_rating', 'total_reviews',
            'package_images', 'day_plans', 'created_at', 'updated_at'
        ]

    def get_average_rating(self, obj):
        from reviews.models import BusReview
        avg = BusReview.objects.filter(bus=obj).aggregate(models.Avg('rating'))['rating__avg']
        return round(avg, 1) if avg is not None else 0.0
    
    def get_total_reviews(self, obj):
        from reviews.models import BusReview
        return BusReview.objects.filter(bus=obj).count()