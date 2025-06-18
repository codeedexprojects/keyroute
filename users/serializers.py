import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite,Wallet
from admin_panel.utils import send_otp
from vendors.models import Bus, Package
from .models import ReferralRewardTransaction
from admin_panel.models import Experience,Sight
from admin_panel.models import *
import calendar
from vendors.models import *
from bookings.serializers import *

User = get_user_model()

class ReferralCodeSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['referral_code', 'price','image']

    def get_price(self, obj):
        refer_and_earn_obj = ReferAndEarn.objects.first()
        return refer_and_earn_obj.price if refer_and_earn_obj else None
    
    def get_image(self, obj):
        refer_and_earn_obj = ReferAndEarn.objects.first()
        if refer_and_earn_obj and refer_and_earn_obj.image:
            return refer_and_earn_obj.image.url
        return None

class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    name = serializers.CharField(max_length=150, required=False)
    referral_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        mobile = data.get('mobile')
        if not mobile:
            raise serializers.ValidationError({"error": "Mobile number is required."})

        try:
            user = User.objects.get(mobile=mobile)
            data['is_new_user'] = False
        except User.DoesNotExist:
            raise serializers.ValidationError({"error": "User with this mobile number does not exist."})
            
        referral_code = data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                if mobile == referrer.mobile:
                    raise serializers.ValidationError({"error": "You cannot refer yourself."})
                data['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"error": "Invalid referral code."})
        
        return data


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    mobile = serializers.CharField(max_length=15)
    referral_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        mobile = data.get('mobile')
        if not mobile:
            raise serializers.ValidationError({"error": "Mobile number is required."})

        if User.objects.filter(mobile=mobile).exists():
            raise serializers.ValidationError({"error": "User with this mobile number already exists."})
        
        if not data.get('name'):
            raise serializers.ValidationError({"error": "Name is required for new users."})
            
        referral_code = data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                if mobile == referrer.mobile:
                    raise serializers.ValidationError({"error": "You cannot refer yourself."})
                data['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"error": "Invalid referral code."})
        
        data['is_new_user'] = True
        return data


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name', 'mobile']

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        referrer = self.context.get('referrer')
        if referrer:
            Wallet.objects.create(
                user=user, 
                referred_by=referrer.mobile,
                referral_used=True
            )
        else:
            Wallet.objects.create(user=user)
        return user


# OTP Session model (Add this to your models.py)
class OTPSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTPSession
        fields = ['id', 'mobile', 'session_id', 'is_new_user', 'name', 'referral_code']
        
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'mobile', 'role', 'referral_code', 'profile_image']
        extra_kwargs = {
            'mobile': {'read_only': True},
            'email': {'required': False},
            'role': {'read_only': True},
            'id': {'read_only': True},
        }

    def validate_email(self, value):
        if value == "":
            return None

        if value and User.objects.filter(email=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)

        if 'email' in validated_data:
            instance.email = validated_data.get('email')

        if 'profile_image' in validated_data:
            instance.profile_image = validated_data.get('profile_image')

        instance.save()
        return instance
    

class BusFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusFeature
        fields = ['id', 'name']    

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon']


class FavouriteSerializer(serializers.ModelSerializer):
    bus_details = serializers.SerializerMethodField(read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Favourite
        fields = ['id', 'user', 'bus', 'package', 'bus_details', 'package_details']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
        }

    def get_bus_details(self, obj):
        if obj.bus:
            return BusListingSerializer(obj.bus).data
        return None
        
    def get_package_details(self, obj):
        if obj.package:
            from bookings.serializers import PackageSerializer
            return PackageSerializer(obj.package).data
        return None

    def create(self, validated_data):
        user = self.context['request'].user if 'request' in self.context else validated_data.get('user')
        if not user and 'user' not in validated_data:
            raise serializers.ValidationError("User is required")
            
        validated_data['user'] = user
        bus = validated_data.get('bus')
        package = validated_data.get('package')

        if bus and package:
            raise serializers.ValidationError("Cannot favorite both bus and package at the same time")
            
        if not bus and not package:
            raise serializers.ValidationError("Either bus or package must be provided")

        if bus:
            favourite, created = Favourite.objects.get_or_create(user=user, bus=bus)
        else:
            favourite, created = Favourite.objects.get_or_create(user=user, package=package)
        return favourite
    
    
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['balance', 'referred_by', 'referral_used']


class OngoingReferralSerializer(serializers.ModelSerializer):
    referred_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ReferralRewardTransaction
        fields = [
            'id',
            'booking_type',
            'booking_id',
            'reward_amount',
            'status',
            'created_at',
            'referrer',
            'referred_user_name'
        ]

    def get_referred_user_name(self, obj):
        return getattr(obj.referred_user, 'name', None)


class ReferralHistorySerializer(serializers.ModelSerializer):
    referred_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ReferralRewardTransaction
        fields = [
            'id',
            'booking_type',
            'booking_id',
            'reward_amount',
            'status',
            'created_at',
            'referrer',
            'referred_user_name'
        ]

    def get_referred_user_name(self, obj):
        return getattr(obj.referred_user, 'name', None)


class ExperienceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperienceImage
        fields = ['id', 'image']

class ExperienceSerializer(serializers.ModelSerializer):
    images = ExperienceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Experience
        fields = ['id', 'sight', 'header', 'sub_header', 'description', 'images']


class SeasonTimeSerializer(serializers.ModelSerializer):
    from_date = serializers.SerializerMethodField()
    to_date = serializers.SerializerMethodField()

    class Meta:
        model = SeasonTime
        fields = '__all__'

    def get_from_date(self, obj):
        return calendar.month_name[obj.from_date.month]

    def get_to_date(self, obj):
        return calendar.month_name[obj.to_date.month]


class SightImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SightImage
        fields = ['id', 'image']


class SightDetailSerializer(serializers.ModelSerializer):
    images = SightImageSerializer(many=True, read_only=True)
    experiences = ExperienceSerializer(many=True, read_only=True)
    seasons = SeasonTimeSerializer(many=True, read_only=True)

    class Meta:
        model = Sight
        fields = ['id', 'title', 'description', 'season_description', 'images', 'experiences', 'seasons']


class SightSerializer(serializers.ModelSerializer):
    images = SightImageSerializer(many=True, read_only=True)

    class Meta:
        model = Sight
        fields = '__all__'


class LimitedDealImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimitedDealImage
        fields = ['id', 'image']

class LimitedDealSerializer(serializers.ModelSerializer):
    images = LimitedDealImageSerializer(many=True, read_only=True)

    class Meta:
        model = LimitedDeal
        fields = ['id', 'title', 'created_at', 'terms_and_conditions', 'offer', 'subtitle', 'images']




class GoogleUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'name', 'mobile', 'is_google_user', 'firebase_uid']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def create(self, validated_data):
        # Create user
        user = User.objects.create(**validated_data)
        
        # Handle referral system
        referrer = self.context.get('referrer')
        if referrer:
            Wallet.objects.create(
                user=user, 
                referred_by=referrer.mobile or referrer.email,  # Use email if mobile not available
                referral_used=True
            )
        else:
            Wallet.objects.create(user=user)
        
        return user
