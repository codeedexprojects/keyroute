import requests
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Favourite,Wallet
from admin_panel.utils import send_otp
from vendors.models import Bus, Package
from .models import ReferralRewardTransaction
from admin_panel.models import Experience,Sight

User = get_user_model()

class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['referral_code']

class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    name = serializers.CharField(max_length=150, required=False)
    referral_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        mobile = data.get('mobile')
        if not mobile:
            raise serializers.ValidationError({"mobile": "Mobile number is required."})

        try:
            user = User.objects.get(mobile=mobile)
            data['is_new_user'] = False
        except User.DoesNotExist:
            raise serializers.ValidationError({"mobile": "User with this mobile number does not exist."})
            
        referral_code = data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                if mobile == referrer.mobile:
                    raise serializers.ValidationError({"referral_code": "You cannot refer yourself."})
                data['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})
        
        return data


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    mobile = serializers.CharField(max_length=15)
    referral_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        mobile = data.get('mobile')
        if not mobile:
            raise serializers.ValidationError({"mobile": "Mobile number is required."})

        if User.objects.filter(mobile=mobile).exists():
            raise serializers.ValidationError({"mobile": "User with this mobile number already exists."})
        
        if not data.get('name'):
            raise serializers.ValidationError({"name": "Name is required for new users."})
            
        referral_code = data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                if mobile == referrer.mobile:
                    raise serializers.ValidationError({"referral_code": "You cannot refer yourself."})
                data['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})
        
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
            Wallet.objects.create(user=user, referred_by=referrer)
        
        return user
        
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

# class ReviewSerializer(serializers.ModelSerializer):
#     user_name = serializers.SerializerMethodField(read_only=True)
    
#     class Meta:
#         model = Review
#         fields = ['id', 'user', 'rating', 'comment', 'created_at', 'user_name']
#         read_only_fields = ['id', 'created_at', 'user_name']
#         extra_kwargs = {
#             'user': {'write_only': True, 'required': False},
#         }
        
#     def get_user_name(self, obj):
#         return obj.user.name if obj.user.name else obj.user.mobile
    
#     def create(self, validated_data):
#         user = self.context['request'].user
#         validated_data['user'] = user
#         return Review.objects.create(**validated_data)

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
            from vendors.serializers import BusSerializer
            return BusSerializer(obj.bus).data
        return None
        
    def get_package_details(self, obj):
        if obj.package:
            from vendors.serializers import PackageSerializer
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

class ExploreSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Experience
        fields = ['__all__']

class SightSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Sight
        fields = ['__all__']